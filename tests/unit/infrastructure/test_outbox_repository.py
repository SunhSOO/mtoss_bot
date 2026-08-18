from uuid import UUID, uuid4

import pytest

from mtoss.infrastructure.db.models.outbox import OutboxEventRecord
from mtoss.infrastructure.db.repositories.outbox import OutboxRepository


class TrackingSession:
    def __init__(
        self, record: OutboxEventRecord, *, failure_point: str | None = None
    ) -> None:
        self.record = record
        self.failure_point = failure_point
        self.calls: list[str] = []

    async def get(
        self, model: type[OutboxEventRecord], event_id: UUID
    ) -> OutboxEventRecord | None:
        self.calls.append("get")
        return self.record

    async def flush(self) -> None:
        self.calls.append("flush")
        if self.failure_point == "flush":
            raise RuntimeError("flush failed")

    async def commit(self) -> None:
        assert self.record.published_at is not None
        self.calls.append("commit")
        if self.failure_point == "commit":
            raise RuntimeError("commit failed")

    async def rollback(self) -> None:
        self.calls.append("rollback")
        self.record.published_at = None


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


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_point", ["flush", "commit"])
async def test_mark_published_rolls_back_flush_and_commit_failures(
    failure_point: str,
) -> None:
    record = OutboxEventRecord(
        id=uuid4(),
        topic="execution.intent.ready",
        message_key="key",
        payload={"intent_id": "intent"},
    )
    session = TrackingSession(record, failure_point=failure_point)

    with pytest.raises(RuntimeError, match=f"{failure_point} failed"):
        await OutboxRepository(session).mark_published(str(record.id))  # type: ignore[arg-type]

    expected = ["get", "flush"]
    if failure_point == "commit":
        expected.append("commit")
    expected.append("rollback")
    assert session.calls == expected
    assert record.published_at is None
