from decimal import Decimal
from uuid import UUID

from mtoss.domain.enums import OrderState
from mtoss.domain.orders import BrokerOrderResult, ExecutionIntent


class FakeBroker:
    """In-memory deterministic broker that deduplicates client order IDs."""

    def __init__(self) -> None:
        self.results: dict[str, BrokerOrderResult] = {}
        self.submitted_keys: list[str] = []

    async def submit(self, intent: ExecutionIntent) -> BrokerOrderResult:
        existing = self.results.get(intent.idempotency_key)
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
        self.results[intent.idempotency_key] = result
        self.submitted_keys.append(intent.idempotency_key)
        return result

    async def lookup_by_client_order_id(
        self, account_id: UUID, client_order_id: str
    ) -> BrokerOrderResult | None:
        return self.results.get(client_order_id)
