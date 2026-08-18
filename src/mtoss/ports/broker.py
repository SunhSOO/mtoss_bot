from typing import Protocol
from uuid import UUID

from mtoss.domain.orders import BrokerOrderResult, ExecutionIntent


class BrokerAdapter(Protocol):
    async def submit(self, intent: ExecutionIntent) -> BrokerOrderResult: ...

    async def lookup_by_client_order_id(
        self, account_id: UUID, client_order_id: str
    ) -> BrokerOrderResult | None: ...
