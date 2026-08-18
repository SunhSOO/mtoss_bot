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
        self.rolled_back = 0

    async def claim(self, limit: int) -> list[dict[str, object]]:
        claimed = self.events[:limit]
        self.events = self.events[limit:]
        return claimed

    async def mark_published(self, event_id: str) -> None:
        self.marked.append(event_id)

    async def rollback(self) -> None:
        self.rolled_back += 1


class FakePublisher:
    async def publish(self, topic: str, key: str, payload: dict[str, object]) -> str:
        return "1-0"


class FailingPublisher:
    async def publish(self, topic: str, key: str, payload: dict[str, object]) -> str:
        raise ConnectionError("redis unavailable")


class RecordingPublisher:
    def __init__(self) -> None:
        self.keys: list[str] = []

    async def publish(self, topic: str, key: str, payload: dict[str, object]) -> str:
        self.keys.append(key)
        return "1-0"


class SequentialOutboxRepository(FakeOutboxRepository):
    def __init__(self) -> None:
        super().__init__()
        self.events.append(
            {
                "id": "2",
                "topic": "execution.intent.ready",
                "message_key": "second",
                "payload": {"intent_id": "second"},
            }
        )
        self.claim_limits: list[int] = []

    async def claim(self, limit: int) -> list[dict[str, object]]:
        self.claim_limits.append(limit)
        return await super().claim(limit)


class FailingMarkRepository(SequentialOutboxRepository):
    async def mark_published(self, event_id: str) -> None:
        self.rolled_back += 1
        raise RuntimeError(f"mark failed for {event_id}")


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


@pytest.mark.asyncio
async def test_failed_publish_rolls_back_claim_before_reraising() -> None:
    repository = FakeOutboxRepository()

    with pytest.raises(ConnectionError, match="redis unavailable"):
        await OutboxDispatcher(repository, FailingPublisher()).dispatch_batch()

    assert repository.marked == []
    assert repository.rolled_back == 1


@pytest.mark.asyncio
async def test_dispatch_batch_claims_and_processes_each_event_once() -> None:
    repository = SequentialOutboxRepository()
    publisher = RecordingPublisher()

    dispatched = await OutboxDispatcher(repository, publisher).dispatch_batch(limit=2)

    assert dispatched == 2
    assert repository.claim_limits == [1, 1]
    assert repository.marked == ["1", "2"]
    assert publisher.keys == ["k", "second"]


@pytest.mark.asyncio
async def test_mark_failure_propagates_without_publishing_later_events() -> None:
    repository = FailingMarkRepository()
    publisher = RecordingPublisher()

    with pytest.raises(RuntimeError, match="mark failed for 1"):
        await OutboxDispatcher(repository, publisher).dispatch_batch(limit=2)

    assert publisher.keys == ["k"]
    assert repository.marked == []
    assert repository.rolled_back == 1
