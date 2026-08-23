import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest

from mtoss.workers.executor import EXECUTION_TOPIC, ExecutionWorker


class FakeOutbox:
    def __init__(self, events: list[dict[str, object]] | None = None) -> None:
        self.pending = events or []
        self.published: list[str] = []
        self.rollbacks = 0
        self.claimed_topics: list[str | None] = []

    async def claim(self, limit: int, topic: str | None = None) -> list[dict[str, object]]:
        self.claimed_topics.append(topic)
        available = [
            event
            for event in self.pending
            if str(event["id"]) not in self.published and event.get("topic") == topic
        ]
        return available[:limit]

    async def mark_published(self, event_id: str) -> None:
        self.published.append(event_id)

    async def rollback(self) -> None:
        self.rollbacks += 1


def event(intent_id: UUID, topic: str = EXECUTION_TOPIC) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "topic": topic,
        "message_key": "k" * 64,
        "payload": {"intent_id": str(intent_id), "account_id": str(uuid4())},
    }


def worker(
    outbox: FakeOutbox,
    execute: object,
    **kwargs: float,
) -> ExecutionWorker:
    @asynccontextmanager
    async def open_outbox() -> AsyncIterator[FakeOutbox]:
        yield outbox

    return ExecutionWorker(open_outbox, execute, **kwargs)  # type: ignore[arg-type]


async def test_nothing_to_do_returns_zero() -> None:
    outbox = FakeOutbox()
    executed: list[UUID] = []

    processed = await worker(outbox, executed.append).run_once()

    assert processed == 0
    assert not executed


async def test_queued_intent_reaches_the_execution_service() -> None:
    """이 경로가 없어서 지금까지 주문이 QUEUED에서 멈춰 있었다."""
    intent_id = uuid4()
    outbox = FakeOutbox([event(intent_id)])
    executed: list[UUID] = []

    async def execute(value: UUID) -> None:
        executed.append(value)

    processed = await worker(outbox, execute).run_once()

    assert processed == 1
    assert executed == [intent_id]
    assert outbox.published


async def test_only_execution_topic_is_claimed() -> None:
    """알림 워커와 같은 테이블을 나눠 쓰므로 남의 이벤트를 삼키면 안 된다."""
    outbox = FakeOutbox([event(uuid4(), topic="notification.requested")])
    executed: list[UUID] = []

    async def execute(value: UUID) -> None:
        executed.append(value)

    assert await worker(outbox, execute).run_once() == 0
    assert not executed
    assert outbox.claimed_topics == [EXECUTION_TOPIC]


async def test_batch_stops_at_the_limit() -> None:
    outbox = FakeOutbox([event(uuid4()) for _ in range(5)])
    executed: list[UUID] = []

    async def execute(value: UUID) -> None:
        executed.append(value)

    assert await worker(outbox, execute).run_once(limit=3) == 3
    assert len(executed) == 3


async def test_transient_failure_leaves_the_event_for_retry() -> None:
    outbox = FakeOutbox([event(uuid4())])

    async def execute(_: UUID) -> None:
        raise ConnectionError("broker unreachable")

    with pytest.raises(ConnectionError):
        await worker(outbox, execute).run_once()

    assert outbox.rollbacks == 1
    assert not outbox.published


async def test_missing_intent_is_consumed_instead_of_looping_forever() -> None:
    """재시도해도 절대 성공하지 않는 행을 남기면 워커가 같은 실패를 무한 반복한다."""
    outbox = FakeOutbox([event(uuid4())])

    async def execute(_: UUID) -> None:
        raise LookupError("intent not found")

    assert await worker(outbox, execute).run_once() == 1
    assert outbox.published
    assert outbox.rollbacks == 0


async def test_missing_risk_evidence_is_also_terminal() -> None:
    outbox = FakeOutbox([event(uuid4())])

    async def execute(_: UUID) -> None:
        raise PermissionError("risk and approval evidence are required")

    assert await worker(outbox, execute).run_once() == 1
    assert outbox.published


async def test_unusable_payload_is_consumed() -> None:
    broken = event(uuid4())
    broken["payload"] = {"intent_id": "not-a-uuid"}
    outbox = FakeOutbox([broken])
    executed: list[UUID] = []

    async def execute(value: UUID) -> None:
        executed.append(value)

    assert await worker(outbox, execute).run_once() == 1
    assert not executed
    assert outbox.published


async def test_run_forever_stops_when_asked() -> None:
    outbox = FakeOutbox([event(uuid4())])
    executed: list[UUID] = []
    stop = asyncio.Event()

    async def execute(value: UUID) -> None:
        executed.append(value)
        stop.set()

    await asyncio.wait_for(
        worker(outbox, execute, poll_interval_seconds=0.01).run_forever(stop), timeout=2
    )

    assert executed


async def test_run_forever_backs_off_instead_of_spinning_on_errors() -> None:
    outbox = FakeOutbox([event(uuid4())])
    attempts = 0
    stop = asyncio.Event()

    async def execute(_: UUID) -> None:
        nonlocal attempts
        attempts += 1
        if attempts >= 2:
            stop.set()
        raise ConnectionError("broker unreachable")

    await asyncio.wait_for(
        worker(
            outbox, execute, poll_interval_seconds=0.01, error_backoff_seconds=0.01
        ).run_forever(stop),
        timeout=2,
    )

    assert attempts >= 2
    assert outbox.rollbacks == attempts
