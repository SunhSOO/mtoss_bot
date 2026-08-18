import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mtoss.application.execution_service import ExecutionService
from mtoss.domain.enums import OrderSide, OrderState
from mtoss.domain.orders import ExecutionIntent
from mtoss.infrastructure.broker.fake import FakeBroker
from mtoss.infrastructure.db.models.audit import AuditEventRecord
from mtoss.infrastructure.db.models.order import OrderIntentRecord
from mtoss.infrastructure.db.models.outbox import OutboxEventRecord
from mtoss.infrastructure.db.repositories.orders import OrderRepository


@pytest.mark.asyncio
async def test_two_execution_attempts_submit_once(db_session, persisted_queued_intent) -> None:
    """Dropping the row lock or saved-state check could double-submit an intent."""
    repository = OrderRepository(db_session)
    fake_broker = FakeBroker()
    service = ExecutionService(repository, fake_broker)

    await service.execute(persisted_queued_intent.intent_id)
    await db_session.commit()
    await service.execute(persisted_queued_intent.intent_id)
    await db_session.commit()
    persisted = await repository.get(persisted_queued_intent.intent_id)

    assert fake_broker.submitted_keys == [persisted_queued_intent.idempotency_key]
    assert persisted is not None
    assert persisted.state is OrderState.SUBMITTED
    assert await repository.count_orders() == 1


@pytest.mark.asyncio
async def test_independent_workers_execute_one_broker_submission() -> None:
    """Removing the PostgreSQL row lock would allow concurrent workers to double-submit."""
    engine = create_async_engine(
        os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss")
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    intent = ExecutionIntent(
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
        idempotency_key="c" * 64,
    )
    risk_decision_id = uuid4()
    approval_id = uuid4()
    persisted_setup = False
    try:
        async with session_factory() as setup_session:
            await OrderRepository(setup_session).create_with_outbox(
                intent,
                OrderState.QUEUED,
                risk_decision_id,
                approval_id,
                {"allowed": True},
                {"status": "APPROVED"},
            )
            await setup_session.commit()
            persisted_setup = True

        fake_broker = FakeBroker()
        async with session_factory() as first_session, session_factory() as second_session:
            first = ExecutionService(OrderRepository(first_session), fake_broker)
            second = ExecutionService(OrderRepository(second_session), fake_broker)
            await asyncio.gather(first.execute(intent.intent_id), second.execute(intent.intent_id))

        async with session_factory() as verification_session:
            persisted = await OrderRepository(verification_session).get(intent.intent_id)
            assert fake_broker.submitted_keys == [intent.idempotency_key]
            assert persisted is not None
            assert persisted.state is OrderState.SUBMITTED
    finally:
        if persisted_setup:
            async with session_factory() as cleanup_session:
                await cleanup_session.execute(
                    delete(OutboxEventRecord).where(
                        OutboxEventRecord.message_key == intent.idempotency_key
                    )
                )
                await cleanup_session.execute(
                    delete(AuditEventRecord).where(AuditEventRecord.trace_id == intent.signal_id)
                )
                await cleanup_session.execute(
                    delete(OrderIntentRecord).where(OrderIntentRecord.id == intent.intent_id)
                )
                await cleanup_session.commit()
        await engine.dispose()
