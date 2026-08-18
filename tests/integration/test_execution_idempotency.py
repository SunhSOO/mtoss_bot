import pytest

from mtoss.application.execution_service import ExecutionService
from mtoss.domain.enums import OrderState
from mtoss.infrastructure.broker.fake import FakeBroker
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
