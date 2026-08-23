"""이격이 커서 예산을 넘는 신호에 대한 사람 확인.

**주문 승인(`approvals`)과 다른 개념이다.** 승인은 "승인 없으면 주문이 안 나간다"이고
인텐트 생성 *안에서* 돈다. 확인은 **수량을 정하는 단계**라 인텐트 생성 *앞에* 있다.

최소 거래 단위(0.01랏)로 사도 리스크 예산을 넘을 때만 뜬다. 그 상황에서는 수량을 더
줄일 방법이 없으므로 자동으로 진행하지 않고 사람에게 넘긴다. **무응답은 건너뛰기다.**
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from mtoss.domain.enums import OrderSide
from mtoss.domain.orders import validate_order_decimal_input


class ConfirmationChoice(StrEnum):
    ENTER = "ENTER"
    """예산 초과를 감수하고 하한 랏으로 진입한다."""

    SKIP = "SKIP"
    """이번 신호를 건너뛴다. 무응답 만료도 결과적으로 같다."""


class ConfirmationState(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"


class NotificationChannel(StrEnum):
    TELEGRAM = "TELEGRAM"
    CONSOLE = "CONSOLE"


class ConfirmationRequest(BaseModel):
    """알림에 실어 보낼 판단 근거 전부."""

    model_config = ConfigDict(frozen=True)

    confirmation_id: UUID
    symbol: str
    side: OrderSide
    bar_close_time: datetime
    stop_price: Decimal
    stop_distance: Decimal
    proposed_lots: Decimal
    risk_amount: Decimal
    budget: Decimal
    equity: Decimal
    deadline_at: datetime

    @field_validator(
        "stop_price",
        "stop_distance",
        "proposed_lots",
        "risk_amount",
        "budget",
        "equity",
        mode="before",
    )
    @classmethod
    def reject_float_amount(cls, value: object) -> object:
        return validate_order_decimal_input(value, "confirmation amount")

    @field_validator("bar_close_time", "deadline_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("confirmation timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @property
    def over_budget_by(self) -> Decimal:
        return max(self.risk_amount - self.budget, Decimal(0))

    @property
    def risk_pct_of_equity(self) -> Decimal:
        if self.equity <= 0:
            return Decimal(0)
        return (self.risk_amount / self.equity * 100).quantize(Decimal("0.1"))

    def is_expired(self, now: datetime) -> bool:
        return now >= self.deadline_at


class ConfirmationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    confirmation_id: UUID
    choice: ConfirmationChoice
    responder: str
    channel: NotificationChannel
    received_at: datetime

    @field_validator("received_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("received_at must be timezone-aware")
        return value.astimezone(UTC)
