import os
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mtoss.infrastructure.db.models.outbox import OutboxEventRecord
from mtoss.infrastructure.db.repositories.outbox import OutboxRepository


@pytest.mark.asyncio
async def test_mark_published_is_visible_to_an_independent_session() -> None:
    engine = create_async_engine(
        os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss")
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    event_id = uuid4()
    setup_committed = False
    try:
        async with session_factory() as setup_session:
            setup_session.add(
                OutboxEventRecord(
                    id=event_id,
                    topic="execution.intent.ready",
                    message_key="key",
                    payload={"intent_id": "intent"},
                )
            )
            await setup_session.commit()
            setup_committed = True

        async with session_factory() as dispatch_session:
            await OutboxRepository(dispatch_session).mark_published(str(event_id))

        async with session_factory() as verification_session:
            persisted = await verification_session.get(OutboxEventRecord, event_id)
            assert persisted is not None
            assert persisted.published_at is not None
    finally:
        if setup_committed:
            async with session_factory() as cleanup_session:
                await cleanup_session.execute(
                    delete(OutboxEventRecord).where(OutboxEventRecord.id == event_id)
                )
                await cleanup_session.commit()
        await engine.dispose()
