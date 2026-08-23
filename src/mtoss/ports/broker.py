from decimal import Decimal
from typing import Protocol
from uuid import UUID

from mtoss.domain.orders import BrokerOrderResult, BrokerPosition, ExecutionIntent


class BrokerAdapter(Protocol):
    """브로커에 대고 할 수 있는 일 전부.

    `submit`/`lookup`만으로는 이 전략을 실을 수 없다. 주문① 익절 후 주문②의 손절을
    본전으로 올리는 동작(`modify_position_sltp`)과, Hull 반전 시 러너만 닫는 동작
    (`close_position`)이 표현되지 않기 때문이다.
    """

    async def submit(self, intent: ExecutionIntent) -> BrokerOrderResult: ...

    async def lookup_by_client_order_id(
        self, account_id: UUID, client_order_id: str
    ) -> BrokerOrderResult | None:
        """`None`은 "보낸 적 없음"을 뜻하며 호출자가 재전송해도 된다는 신호다.

        모르겠으면 절대 `None`을 돌려주지 말 것. 확신이 없으면 `UNKNOWN` 상태의
        결과를 돌려줘야 중복주문이 나지 않는다.
        """
        ...

    async def modify_position_sltp(
        self,
        account_id: UUID,
        position_ref: str,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
    ) -> BrokerPosition:
        """이미 열린 포지션의 손절·익절만 바꾼다. 수량은 건드리지 않는다."""
        ...

    async def close_position(
        self, account_id: UUID, position_ref: str, quantity: Decimal | None = None
    ) -> BrokerOrderResult:
        """포지션을 닫는다. `quantity`가 `None`이면 전량."""
        ...

    async def list_positions(self, account_id: UUID) -> tuple[BrokerPosition, ...]:
        """브로커가 실제로 들고 있는 포지션. 정합성 조정의 기준이다."""
        ...
