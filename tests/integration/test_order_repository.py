from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from mtoss.domain.enums import OrderSide, OrderState
from mtoss.domain.orders import ExecutionIntent
from mtoss.infrastructure.db.repositories.orders import OrderRepository


@pytest.mark.asyncio
@pytest.mark.parametrize("_attempt", [1, 2])
async def test_intent_and_outbox_are_atomic_and_idempotent(db_session, _attempt: int) -> None:
    intent = ExecutionIntent(
        intent_id=uuid4(),
        account_id=uuid4(),
        signal_id=uuid4(),
        target_version=1,
        market="US",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        limit_price=Decimal("225.10"),
        currency="USD",
        expires_at=datetime.now(UTC) + timedelta(seconds=90),
        idempotency_key="1" * 64,
    )
    repository = OrderRepository(db_session)
    await repository.create_with_outbox(
        intent,
        OrderState.QUEUED,
        uuid4(),
        uuid4(),
        {"allowed": True},
        {"status": "APPROVED"},
    )
    await db_session.commit()
    assert await repository.count_orders() == 1
    assert await repository.count_unpublished_outbox() == 1
    assert await repository.count_audit_events() == 2

    with pytest.raises(IntegrityError):
        await repository.create_with_outbox(
            intent.model_copy(update={"intent_id": uuid4()}),
            OrderState.QUEUED,
            uuid4(),
            uuid4(),
            {"allowed": True},
            {"status": "APPROVED"},
        )
    await db_session.rollback()
