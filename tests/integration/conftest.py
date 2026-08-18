import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mtoss.domain.enums import OrderSide, OrderState
from mtoss.domain.orders import ExecutionIntent
from mtoss.infrastructure.db.repositories.orders import OrderRepository


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss")
    )
    try:
        async with engine.connect() as connection:
            outer_transaction = await connection.begin()
            factory = async_sessionmaker(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            async with factory() as session:
                try:
                    yield session
                finally:
                    await session.rollback()
            await outer_transaction.rollback()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def persisted_queued_intent(db_session) -> ExecutionIntent:
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
        idempotency_key="b" * 64,
    )
    await OrderRepository(db_session).create_with_outbox(
        intent,
        OrderState.QUEUED,
        uuid4(),
        uuid4(),
        {"allowed": True},
        {"status": "APPROVED"},
    )
    await db_session.commit()
    return intent
