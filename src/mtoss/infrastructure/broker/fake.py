from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from mtoss.domain.enums import OrderState
from mtoss.domain.orders import BrokerOrderResult, BrokerPosition, ExecutionIntent


class FakeBroker:
    """멱등키로 중복을 걸러 내는 결정적 인메모리 브로커.

    헤징 계좌를 흉내 낸다 — 주문 하나가 포지션 하나가 되고 각자 SL/TP를 갖는다.
    실브로커를 붙이기 전에 배관 전체를 돌려 보기 위한 것이다.
    """

    def __init__(self) -> None:
        self.results: dict[tuple[UUID, str], BrokerOrderResult] = {}
        self.positions: dict[tuple[UUID, str], BrokerPosition] = {}
        self.submitted_keys: list[str] = []

    async def submit(self, intent: ExecutionIntent) -> BrokerOrderResult:
        key = (intent.account_id, intent.idempotency_key)
        existing = self.results.get(key)
        if existing is not None:
            return existing

        sequence = len(self.results) + 1
        result = BrokerOrderResult(
            client_order_id=intent.idempotency_key,
            broker_order_id=f"fake-{sequence}",
            state=OrderState.SUBMITTED,
            filled_quantity=Decimal("0"),
            average_price=None,
            broker_request_id=f"fake-request-{sequence}",
        )
        self.results[key] = result
        self.submitted_keys.append(intent.idempotency_key)

        if not intent.reduce_only and intent.pricing_reference is not None:
            position_ref = f"fake-position-{sequence}"
            self.positions[(intent.account_id, position_ref)] = BrokerPosition(
                position_ref=position_ref,
                account_id=intent.account_id,
                symbol=intent.symbol,
                side=intent.side,
                quantity=intent.quantity,
                entry_price=intent.pricing_reference,
                stop_loss=intent.stop_loss,
                take_profit=intent.take_profit,
                tranche_ref=intent.tranche_ref,
                opened_at=datetime.now(UTC),
            )
        return result

    async def lookup_by_client_order_id(
        self, account_id: UUID, client_order_id: str
    ) -> BrokerOrderResult | None:
        return self.results.get((account_id, client_order_id))

    async def modify_position_sltp(
        self,
        account_id: UUID,
        position_ref: str,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
    ) -> BrokerPosition:
        position = self.positions.get((account_id, position_ref))
        if position is None:
            raise KeyError(f"unknown position {position_ref}")
        updated = position.model_copy(
            update={"stop_loss": stop_loss, "take_profit": take_profit}
        )
        self.positions[(account_id, position_ref)] = updated
        return updated

    async def close_position(
        self, account_id: UUID, position_ref: str, quantity: Decimal | None = None
    ) -> BrokerOrderResult:
        position = self.positions.get((account_id, position_ref))
        if position is None:
            raise KeyError(f"unknown position {position_ref}")

        closing = position.quantity if quantity is None else quantity
        if closing > position.quantity:
            raise ValueError("cannot close more than the open quantity")

        remaining = position.quantity - closing
        if remaining > 0:
            self.positions[(account_id, position_ref)] = position.model_copy(
                update={"quantity": remaining}
            )
        else:
            del self.positions[(account_id, position_ref)]

        return BrokerOrderResult(
            client_order_id=position_ref,
            broker_order_id=f"fake-close-{position_ref}",
            state=OrderState.FILLED,
            filled_quantity=closing,
            average_price=position.entry_price,
            broker_request_id=None,
        )

    async def list_positions(self, account_id: UUID) -> tuple[BrokerPosition, ...]:
        return tuple(
            position
            for (owner, _), position in self.positions.items()
            if owner == account_id
        )
