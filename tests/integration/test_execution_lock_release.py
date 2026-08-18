import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mtoss.application.execution_service import ExecutionService
from mtoss.domain.enums import OrderSide, OrderState
from mtoss.domain.orders import BrokerOrderResult, ExecutionIntent
from mtoss.infrastructure.db.models.audit import AuditEventRecord
from mtoss.infrastructure.db.models.order import OrderIntentRecord
from mtoss.infrastructure.db.models.outbox import OutboxEventRecord
from mtoss.infrastructure.db.repositories.orders import OrderRepository


class ScenarioRepository(OrderRepository):
    def __init__(self, session, scenario: str) -> None:
        super().__init__(session)
        self.scenario = scenario

    async def lock_for_execution(self, intent_id: UUID) -> OrderIntentRecord:
        record = await super().lock_for_execution(intent_id)
        if self.scenario == "missing_evidence":
            record.risk_decision_id = None  # type: ignore[assignment]
        elif self.scenario == "lock_error":
            raise LookupError(str(intent_id))
        return record


class ScenarioBroker:
    def __init__(self, scenario: str) -> None:
        self.scenario = scenario

    async def lookup_by_client_order_id(
        self, account_id: UUID, client_order_id: str
    ) -> BrokerOrderResult | None:
        if self.scenario == "lookup_identity_failure":
            return BrokerOrderResult(
                client_order_id="f" * 64,
                broker_order_id="wrong-order",
                state=OrderState.SUBMITTED,
                filled_quantity=Decimal("0"),
                average_price=None,
                broker_request_id="wrong-request",
            )
        return None

    async def submit(self, intent: ExecutionIntent) -> BrokerOrderResult:
        if self.scenario == "broker_exception":
            raise RuntimeError("broker unavailable")
        return BrokerOrderResult(
            client_order_id=intent.idempotency_key,
            broker_order_id="broker-order",
            state=OrderState.SUBMITTED,
            filled_quantity=Decimal("0"),
            average_price=None,
            broker_request_id="broker-request",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    [
        "non_queued",
        "missing_evidence",
        "lookup_identity_failure",
        "broker_exception",
        "lock_error",
    ],
)
async def test_early_and_error_paths_release_row_lock_for_independent_session(
    scenario: str,
) -> None:
    """Without service-owned rollback the second SELECT FOR UPDATE times out."""
    engine = create_async_engine(
        os.getenv(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss",
        )
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
        idempotency_key="e" * 64,
    )
    initial_state = (
        OrderState.SUBMITTED if scenario == "non_queued" else OrderState.QUEUED
    )
    setup_committed = False
    try:
        async with session_factory() as setup_session:
            await OrderRepository(setup_session).create_with_outbox(
                intent,
                initial_state,
                uuid4(),
                uuid4(),
                {"allowed": True},
                {"status": "APPROVED"},
            )
            await setup_session.commit()
            setup_committed = True

        async with session_factory() as first_session, session_factory() as second_session:
            service = ExecutionService(
                ScenarioRepository(first_session, scenario),
                ScenarioBroker(scenario),
            )
            if scenario == "non_queued":
                await service.execute(intent.intent_id)
            else:
                with pytest.raises((LookupError, PermissionError, RuntimeError, ValueError)):
                    await service.execute(intent.intent_id)

            second_record = await asyncio.wait_for(
                OrderRepository(second_session).lock_for_execution(intent.intent_id),
                timeout=1,
            )
            assert second_record.id == intent.intent_id
            await second_session.rollback()
    finally:
        if setup_committed:
            async with session_factory() as cleanup_session:
                await cleanup_session.execute(
                    delete(OutboxEventRecord).where(
                        OutboxEventRecord.message_key == intent.idempotency_key
                    )
                )
                await cleanup_session.execute(
                    delete(AuditEventRecord).where(
                        AuditEventRecord.trace_id == intent.signal_id
                    )
                )
                await cleanup_session.execute(
                    delete(OrderIntentRecord).where(
                        OrderIntentRecord.id == intent.intent_id
                    )
                )
                await cleanup_session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_not_found_releases_transaction_before_independent_session_query() -> None:
    engine = create_async_engine(
        os.getenv(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss",
        )
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    missing_id = uuid4()
    try:
        async with session_factory() as first_session, session_factory() as second_session:
            with pytest.raises(LookupError, match=str(missing_id)):
                await ExecutionService(
                    OrderRepository(first_session), ScenarioBroker("not_found")
                ).execute(missing_id)
            assert not first_session.in_transaction()
            assert await asyncio.wait_for(second_session.scalar(select(1)), timeout=1) == 1
            await second_session.rollback()
    finally:
        await engine.dispose()
