import pytest

from mtoss.application.outbox_dispatcher import OutboxDispatcher


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.events = [
            {
                "id": "1",
                "topic": "execution.intent.ready",
                "message_key": "k",
                "payload": {"intent_id": "i"},
            }
        ]
        self.marked: list[str] = []

    async def claim(self, limit: int) -> list[dict[str, object]]:
        return self.events[:limit]

    async def mark_published(self, event_id: str) -> None:
        self.marked.append(event_id)


class FakePublisher:
    async def publish(self, topic: str, key: str, payload: dict[str, object]) -> str:
        return "1-0"


class FailingPublisher:
    async def publish(self, topic: str, key: str, payload: dict[str, object]) -> str:
        raise ConnectionError("redis unavailable")


@pytest.mark.asyncio
async def test_dispatch_marks_only_published_events() -> None:
    repository = FakeOutboxRepository()

    dispatched = await OutboxDispatcher(repository, FakePublisher()).dispatch_once()

    assert dispatched == 1
    assert repository.marked == ["1"]


@pytest.mark.asyncio
async def test_failed_publish_is_not_marked() -> None:
    repository = FakeOutboxRepository()

    with pytest.raises(ConnectionError, match="redis unavailable"):
        await OutboxDispatcher(repository, FailingPublisher()).dispatch_once()

    assert repository.marked == []
