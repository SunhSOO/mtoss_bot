from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from mtoss.domain.enums import OrderSide, OrderState
from mtoss.domain.orders import BrokerOrderResult
from mtoss.infrastructure.db.models.order import OrderIntentRecord
from mtoss.infrastructure.db.repositories.orders import OrderRepository


def make_record() -> OrderIntentRecord:
    return OrderIntentRecord(
        id=uuid4(),
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
        idempotency_key="d" * 64,
        state=OrderState.QUEUED,
        broker_order_id=None,
        filled_quantity=Decimal("0"),
        average_price=None,
        broker_request_id=None,
        error_code=None,
        risk_decision_id=uuid4(),
        approval_id=uuid4(),
    )


def immediate_fill(record: OrderIntentRecord) -> BrokerOrderResult:
    return BrokerOrderResult(
        client_order_id=record.idempotency_key,
        broker_order_id="broker-fill-1",
        state=OrderState.FILLED,
        filled_quantity=Decimal("1"),
        average_price=Decimal("225"),
        broker_request_id="request-fill-1",
    )


class ExecutionSession:
    def __init__(self, record: OrderIntentRecord, *, fail_commit: bool = False) -> None:
        self.record = record
        self.fail_commit = fail_commit
        self.calls: list[str] = []
        self.snapshot = (
            record.state,
            record.broker_order_id,
            record.filled_quantity,
            record.average_price,
            record.broker_request_id,
            record.error_code,
        )

    async def scalar(self, statement: object) -> OrderIntentRecord:
        self.calls.append("scalar")
        return self.record

    async def flush(self) -> None:
        self.calls.append("flush")

    async def commit(self) -> None:
        self.calls.append("commit")
        if self.fail_commit:
            raise RuntimeError("commit failed")

    async def rollback(self) -> None:
        self.calls.append("rollback")
        (
            self.record.state,
            self.record.broker_order_id,
            self.record.filled_quantity,
            self.record.average_price,
            self.record.broker_request_id,
            self.record.error_code,
        ) = self.snapshot


@pytest.mark.asyncio
async def test_immediate_fill_is_committed_once_after_atomic_synthetic_transitions() -> None:
    """Committing the synthetic SUBMITTED state separately leaves an unreconciled intermediate."""
    record = make_record()
    session = ExecutionSession(record)

    await OrderRepository(session).save_broker_result(record.id, immediate_fill(record))  # type: ignore[arg-type]

    assert record.state is OrderState.FILLED
    assert record.filled_quantity == Decimal("1")
    assert session.calls == ["scalar", "flush", "commit"]


@pytest.mark.asyncio
async def test_failed_atomic_immediate_fill_commit_rolls_back_without_submitted_state() -> None:
    """A failed final commit must not leave a durable synthetic SUBMITTED state."""
    record = make_record()
    session = ExecutionSession(record, fail_commit=True)

    with pytest.raises(RuntimeError, match="commit failed"):
        await OrderRepository(session).save_broker_result(record.id, immediate_fill(record))  # type: ignore[arg-type]

    assert record.state is OrderState.QUEUED
    assert record.broker_order_id is None
    assert record.filled_quantity == Decimal("0")
    assert session.calls == ["scalar", "flush", "commit", "rollback"]


@pytest.mark.asyncio
async def test_mismatched_result_identity_rolls_back_before_mutating_record() -> None:
    """Repository persistence must not trust service-side identity validation alone."""
    record = make_record()
    session = ExecutionSession(record)
    mismatched = immediate_fill(record).model_copy(
        update={"client_order_id": "e" * 64}
    )

    with pytest.raises(ValueError, match="client order ID does not match"):
        await OrderRepository(session).save_broker_result(record.id, mismatched)  # type: ignore[arg-type]

    assert record.state is OrderState.QUEUED
    assert record.broker_order_id is None
    assert record.filled_quantity == Decimal("0")
    assert session.calls == ["scalar", "rollback"]


@pytest.mark.asyncio
async def test_release_execution_lock_rolls_back_session_transaction() -> None:
    record = make_record()
    session = ExecutionSession(record)

    await OrderRepository(session).release_execution_lock()  # type: ignore[arg-type]

    assert session.calls == ["rollback"]
