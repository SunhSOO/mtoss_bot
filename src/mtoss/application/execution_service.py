from decimal import Decimal
from typing import Protocol
from uuid import UUID

from mtoss.domain.enums import OrderState
from mtoss.domain.orders import BrokerOrderResult, ExecutionIntent
from mtoss.ports.broker import BrokerAdapter


class ExecutionRecord(Protocol):
    id: UUID
    state: OrderState
    risk_decision_id: UUID | None
    approval_id: UUID | None

    def as_domain(self) -> ExecutionIntent: ...

    def as_broker_result(self) -> BrokerOrderResult: ...


class ExecutionRepository(Protocol):
    async def lock_for_execution(self, intent_id: UUID) -> ExecutionRecord: ...

    async def save_broker_result(self, intent_id: UUID, result: BrokerOrderResult) -> None: ...


class ExecutionService:
    def __init__(self, repository: ExecutionRepository, broker: BrokerAdapter) -> None:
        self.repository = repository
        self.broker = broker

    async def execute(self, intent_id: UUID) -> BrokerOrderResult:
        record = await self.repository.lock_for_execution(intent_id)
        if record.risk_decision_id is None or record.approval_id is None:
            raise PermissionError("risk and approval evidence are required")
        if record.state is not OrderState.QUEUED:
            return record.as_broker_result()

        intent = record.as_domain()
        known = await self.broker.lookup_by_client_order_id(
            intent.account_id, intent.idempotency_key
        )
        if known is not None:
            return await self._persist_result(intent_id, known)
        try:
            result = await self.broker.submit(intent)
        except TimeoutError:
            known = await self.broker.lookup_by_client_order_id(
                intent.account_id, intent.idempotency_key
            )
            result = known or BrokerOrderResult(
                client_order_id=intent.idempotency_key,
                broker_order_id=None,
                state=OrderState.UNKNOWN,
                filled_quantity=Decimal("0"),
                average_price=None,
                broker_request_id=None,
                error_code="AMBIGUOUS_TIMEOUT",
            )
        return await self._persist_result(intent_id, result)

    async def _persist_result(
        self, intent_id: UUID, result: BrokerOrderResult
    ) -> BrokerOrderResult:
        if result.state in {
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCELED,
        }:
            await self.repository.save_broker_result(
                intent_id, result.model_copy(update={"state": OrderState.SUBMITTED})
            )
        await self.repository.save_broker_result(intent_id, result)
        return result
