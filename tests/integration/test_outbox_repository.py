from uuid import uuid4

import pytest

from mtoss.infrastructure.db.models.outbox import OutboxEventRecord
from mtoss.infrastructure.db.repositories.outbox import OutboxRepository


@pytest.mark.asyncio
async def test_mark_published_persists_timestamp(db_session) -> None:
    record = OutboxEventRecord(
        id=uuid4(),
        topic="execution.intent.ready",
        message_key="key",
        payload={"intent_id": "intent"},
    )
    db_session.add(record)
    await db_session.flush()

    await OutboxRepository(db_session).mark_published(str(record.id))

    await db_session.refresh(record)
    assert record.published_at is not None
