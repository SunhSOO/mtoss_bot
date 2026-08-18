from uuid import UUID, uuid4

import pytest

from mtoss.infrastructure.db.models.outbox import OutboxEventRecord
from mtoss.infrastructure.db.repositories.outbox import OutboxRepository


class TrackingSession:
    def __init__(self, record: OutboxEventRecord) -> None:
        self.record = record
        self.calls: list[str] = []

    async def get(
        self, model: type[OutboxEventRecord], event_id: UUID
    ) -> OutboxEventRecord | None:
        self.calls.append("get")
        return self.record

    async def flush(self) -> None:
        self.calls.append("flush")

    async def commit(self) -> None:
        assert self.record.published_at is not None
        self.calls.append("commit")


@pytest.mark.asyncio
async def test_mark_published_commits_after_updating_existing_record() -> None:
    record = OutboxEventRecord(
        id=uuid4(),
        topic="execution.intent.ready",
        message_key="key",
        payload={"intent_id": "intent"},
    )
    session = TrackingSession(record)

    await OutboxRepository(session).mark_published(str(record.id))  # type: ignore[arg-type]

    assert record.published_at is not None
    assert session.calls == ["get", "flush", "commit"]
