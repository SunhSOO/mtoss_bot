from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from mtoss.domain.enums import OrderSide, OrderState
from mtoss.domain.orders import BrokerOrderResult, ExecutionIntent


class StubRecord:
    def __init__(
        self,
        *,
        state: OrderState = OrderState.QUEUED,
        risk_decision_id: UUID | None = None,
        approval_id: UUID | None = None,
    ) -> None:
        self.intent = ExecutionIntent(
            intent_id=uuid4(),
            account_id=uuid4(),
            signal_id=uuid4(),
            target_version=1,
            market="US",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            limit_price=Decimal("225"),
            currency="USD",
            expires_at=datetime.now(UTC) + timedelta(seconds=90),
            idempotency_key="a" * 64,
        )
        self.id = self.intent.intent_id
        self.state = state
        self.risk_decision_id = risk_decision_id if risk_decision_id is not None else uuid4()
        self.approval_id = approval_id if approval_id is not None else uuid4()
        self.broker_order_id: str | None = None
        self.filled_quantity = Decimal("0")
        self.average_price: Decimal | None = None
        self.broker_request_id: str | None = None
        self.error_code: str | None = None

    def as_domain(self) -> ExecutionIntent:
        return self.intent

    def as_broker_result(self) -> BrokerOrderResult:
        return BrokerOrderResult(
            client_order_id=self.intent.idempotency_key,
            broker_order_id=self.broker_order_id,
            state=self.state,
            filled_quantity=self.filled_quantity,
            average_price=self.average_price,
            broker_request_id=self.broker_request_id,
            error_code=self.error_code,
        )


class FakeRepository:
    def __init__(self, record: StubRecord) -> None:
        self.record = record
        self.saved: list[BrokerOrderResult] = []

    async def lock_for_execution(self, intent_id: UUID) -> StubRecord:
        assert intent_id == self.record.id
        return self.record

    async def save_broker_result(self, intent_id: UUID, result: BrokerOrderResult) -> None:
        assert intent_id == self.record.id
        self.saved.append(result)
        self.record.state = result.state
        self.record.broker_order_id = result.broker_order_id
        self.record.filled_quantity = result.filled_quantity
        self.record.average_price = result.average_price
        self.record.broker_request_id = result.broker_request_id
        self.record.error_code = result.error_code


class CountingBroker:
    def __init__(self) -> None:
        self.submissions: list[str] = []
        self.lookups: list[tuple[UUID, str]] = []

    async def submit(self, intent: ExecutionIntent) -> BrokerOrderResult:
        self.submissions.append(intent.idempotency_key)
        return BrokerOrderResult(
            client_order_id=intent.idempotency_key,
            broker_order_id="fake-1",
            state=OrderState.SUBMITTED,
            filled_quantity=Decimal("0"),
            average_price=None,
            broker_request_id="request-1",
        )

    async def lookup_by_client_order_id(
        self, account_id: UUID, client_order_id: str
    ) -> BrokerOrderResult | None:
        self.lookups.append((account_id, client_order_id))
        return None


@pytest.mark.asyncio
async def test_execute_submits_eligible_queued_intent_only_once() -> None:
    """Removing the saved-state check would submit the same intent twice."""
    from mtoss.application.execution_service import ExecutionService

    record = StubRecord()
    repository = FakeRepository(record)
    broker = CountingBroker()
    service = ExecutionService(repository, broker)

    first = await service.execute(record.id)
    second = await service.execute(record.id)

    assert first.state is OrderState.SUBMITTED
    assert second == first
    assert broker.submissions == [record.intent.idempotency_key]
    assert repository.saved == [first]


@pytest.mark.asyncio
async def test_execute_rejects_queued_intent_without_risk_evidence() -> None:
    """Removing evidence validation would send an unaudited queued intent."""
    from mtoss.application.execution_service import ExecutionService

    record = StubRecord()
    record.risk_decision_id = None
    repository = FakeRepository(record)
    broker = CountingBroker()

    with pytest.raises(PermissionError, match="risk and approval evidence"):
        await ExecutionService(repository, broker).execute(record.id)

    assert broker.submissions == []
    assert repository.saved == []


class TimeoutBroker(CountingBroker):
    async def submit(self, intent: ExecutionIntent) -> BrokerOrderResult:
        self.submissions.append(intent.idempotency_key)
        raise TimeoutError("response lost")


@pytest.mark.asyncio
async def test_timeout_looks_up_existing_broker_order_before_persisting_result() -> None:
    """Skipping timeout lookup would discard a broker order whose response was lost."""
    from mtoss.application.execution_service import ExecutionService

    record = StubRecord()
    known = BrokerOrderResult(
        client_order_id=record.intent.idempotency_key,
        broker_order_id="broker-known",
        state=OrderState.SUBMITTED,
        filled_quantity=Decimal("0"),
        average_price=None,
        broker_request_id="request-known",
    )

    class TimeoutThenKnownBroker(TimeoutBroker):
        async def lookup_by_client_order_id(
            self, account_id: UUID, client_order_id: str
        ) -> BrokerOrderResult | None:
            self.lookups.append((account_id, client_order_id))
            return known

    repository = FakeRepository(record)
    broker = TimeoutThenKnownBroker()

    result = await ExecutionService(repository, broker).execute(record.id)

    assert result == known
    assert broker.lookups == [(record.intent.account_id, record.intent.idempotency_key)]
    assert repository.saved == [known]


@pytest.mark.asyncio
async def test_timeout_without_known_broker_order_becomes_unknown_without_resubmitting() -> None:
    """Re-queuing UNKNOWN would risk duplicate broker submission after an ambiguous timeout."""
    from mtoss.application.execution_service import ExecutionService

    record = StubRecord()
    repository = FakeRepository(record)
    broker = TimeoutBroker()
    service = ExecutionService(repository, broker)

    first = await service.execute(record.id)
    second = await service.execute(record.id)

    assert first.state is OrderState.UNKNOWN
    assert first.error_code == "AMBIGUOUS_TIMEOUT"
    assert second == first
    assert broker.submissions == [record.intent.idempotency_key]
    assert repository.saved == [first]
