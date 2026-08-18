from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from mtoss.domain.enums import OrderSide, OrderState
from mtoss.domain.orders import ExecutionIntent


def make_intent() -> ExecutionIntent:
    return ExecutionIntent(
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


@pytest.mark.asyncio
async def test_fake_broker_reuses_result_for_same_client_order_id() -> None:
    """Creating another result for a duplicate key would violate fake broker idempotency."""
    from mtoss.infrastructure.broker.fake import FakeBroker

    broker = FakeBroker()
    intent = make_intent()

    first = await broker.submit(intent)
    second = await broker.submit(intent)
    looked_up = await broker.lookup_by_client_order_id(intent.account_id, intent.idempotency_key)

    assert first == second == looked_up
    assert first.state is OrderState.SUBMITTED
    assert broker.submitted_keys == [intent.idempotency_key]


@pytest.mark.asyncio
async def test_fake_broker_lookup_is_scoped_to_the_requested_account() -> None:
    """Returning a same-key result from another account could reconcile the wrong order."""
    from mtoss.infrastructure.broker.fake import FakeBroker

    broker = FakeBroker()
    first_account_intent = make_intent()
    other_account_intent = first_account_intent.model_copy(update={"account_id": uuid4()})

    await broker.submit(first_account_intent)
    result = await broker.lookup_by_client_order_id(
        other_account_intent.account_id, other_account_intent.idempotency_key
    )

    assert result is None
