"""멱등키와 MT5 주문을 잇는 선행기록(write-ahead) 계층.

MT5에는 client-order-id 필드가 **없다.** 우리 멱등키는 sha256 64자인데 `comment`는
31자 제한이고 브로커가 덮어쓰기까지 한다. 단일 수단은 전부 실패한다.

- `comment` 단독: 길이 부족 + 브로커가 `[sl]` 등을 붙이며 변조
- `magic` 단독: 보냈는지는 알아도 **"안 보냄"과 "보냈는데 히스토리 미동기"를 구분 못 함**
- 히스토리 시간창 스캔 단독: 수동매매가 섞이고, MT5 시각은 UTC가 아니라 서버 시각
- 로컬 테이블 단독: `order_send` 반환 직후~UPDATE 커밋 직전 크래시를 못 잡음

그래서 셋을 겹쳐 쓴다.

- **선행기록 테이블 = 게이트.** `order_send` **전에** 커밋한다. 이 행이 없으면
  "보낸 적 없음"이 증명되고, 있으면 "보냈을 수도 있음"이다.
- **magic = 해석기.** 주문·거래·포지션 모두에 남아 히스토리 스캔으로 티켓을 찾는다.
- **comment = 장식.** 사람이 터미널에서 알아보기 위한 것일 뿐 절대 신뢰하지 않는다.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from mtoss.domain.enums import OrderSide

MAGIC_MASK = 0x7FFF_FFFF_FFFF_FFFF
"""63비트. MT5는 요청에서 `ulong`으로 받지만 조회 때 signed `long`으로 돌려주므로,
최상위 비트를 비워야 왕복하며 부호가 뒤집히지 않는다."""

COMMENT_LENGTH = 16
"""`comment`는 31자 제한이고 브로커가 `[sl]` 같은 접미사를 덧붙인다. 16자면 안전하다."""


def magic_for(idempotency_key: str) -> int:
    """멱등키 앞 16자(64비트)를 63비트로 눌러 magic으로 쓴다.

    수명 10만 건 기준 충돌 확률은 5e-10 수준이고, `UNIQUE(mt5_login, magic)`이
    받쳐 주므로 충돌해도 조용히 재사용되지 않고 예외가 난다.
    """
    prefix = idempotency_key[:16]
    if len(prefix) < 16 or any(character not in "0123456789abcdef" for character in prefix):
        raise ValueError("idempotency_key must be a lowercase SHA-256 hex digest")
    return int(prefix, 16) & MAGIC_MASK


def comment_for(idempotency_key: str) -> str:
    return idempotency_key[:COMMENT_LENGTH]


class Mt5OrderLink(BaseModel):
    model_config = ConfigDict(frozen=True)

    idempotency_key: str
    intent_id: UUID
    account_id: UUID
    mt5_login: int
    magic: int
    broker_symbol: str
    side: OrderSide
    requested_lots: Decimal

    submit_started_at: datetime
    """`order_send` **직전**에 커밋된 시각. 복구 스캔의 기준점이다."""

    order_ticket: int | None = None
    deal_ticket: int | None = None
    position_id: int | None = None
    retcode: int | None = None
    resolved_at: datetime | None = None

    @field_validator("idempotency_key")
    @classmethod
    def require_sha256_key(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("idempotency_key must be a lowercase SHA-256 hex digest")
        return value

    @field_validator("magic")
    @classmethod
    def require_63_bit_magic(cls, value: int) -> int:
        if not 0 <= value <= MAGIC_MASK:
            raise ValueError("magic must fit in 63 bits so it survives a signed round trip")
        return value

    @field_validator("submit_started_at", "resolved_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("link timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @property
    def is_resolved(self) -> bool:
        return self.order_ticket is not None or self.deal_ticket is not None


class Mt5LinkStore(Protocol):
    """선행기록 저장소.

    `reserve`는 **호출자의 트랜잭션과 분리된 짧은 세션에서 즉시 커밋**해야 한다.
    `ExecutionService`가 `SELECT FOR UPDATE`를 쥔 트랜잭션을 공유하면, 크래시 시
    선행기록이 함께 롤백돼 "보내려던 참이었다"는 유일한 증거가 사라진다.
    """

    async def reserve(self, link: Mt5OrderLink) -> Mt5OrderLink:
        """행을 만들고 커밋한다. 이미 있으면 **기존 행을 그대로 돌려준다.**

        재시도로 같은 키가 다시 와도 새 magic을 발급하면 안 된다.
        """
        ...

    async def get(self, account_id: UUID, idempotency_key: str) -> Mt5OrderLink | None: ...

    async def record_result(
        self,
        idempotency_key: str,
        *,
        order_ticket: int | None,
        deal_ticket: int | None,
        position_id: int | None,
        retcode: int | None,
    ) -> Mt5OrderLink: ...


class InMemoryLinkStore:
    """테스트와 FakeBroker 경로용. 커밋 경계가 없으므로 실거래에 쓰지 말 것."""

    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, str], Mt5OrderLink] = {}

    async def reserve(self, link: Mt5OrderLink) -> Mt5OrderLink:
        key = (link.account_id, link.idempotency_key)
        existing = self.rows.get(key)
        if existing is not None:
            return existing
        clash = [
            row
            for row in self.rows.values()
            if row.mt5_login == link.mt5_login and row.magic == link.magic
        ]
        if clash:
            raise ValueError(f"magic {link.magic} already reserved on login {link.mt5_login}")
        self.rows[key] = link
        return link

    async def get(self, account_id: UUID, idempotency_key: str) -> Mt5OrderLink | None:
        return self.rows.get((account_id, idempotency_key))

    async def record_result(
        self,
        idempotency_key: str,
        *,
        order_ticket: int | None,
        deal_ticket: int | None,
        position_id: int | None,
        retcode: int | None,
    ) -> Mt5OrderLink:
        for key, row in self.rows.items():
            if row.idempotency_key != idempotency_key:
                continue
            updated = row.model_copy(
                update={
                    "order_ticket": order_ticket,
                    "deal_ticket": deal_ticket,
                    "position_id": position_id,
                    "retcode": retcode,
                    "resolved_at": datetime.now(UTC),
                }
            )
            self.rows[key] = updated
            return updated
        raise LookupError(idempotency_key)
