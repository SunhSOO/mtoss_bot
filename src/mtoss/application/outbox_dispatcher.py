from typing import Protocol, cast

from mtoss.ports.event_publisher import EventPublisher


class OutboxRepositoryPort(Protocol):
    async def claim(self, limit: int) -> list[dict[str, object]]: ...

    async def mark_published(self, event_id: str) -> None: ...

    async def rollback(self) -> None: ...


class OutboxDispatcher:
    def __init__(self, repository: OutboxRepositoryPort, publisher: EventPublisher) -> None:
        self.repository = repository
        self.publisher = publisher

    async def dispatch_once(self, limit: int = 100) -> int:
        return await self.dispatch_batch(limit)

    async def dispatch_batch(self, limit: int = 100) -> int:
        count = 0
        while count < limit:
            events = await self.repository.claim(1)
            if not events:
                break
            event = events[0]
            payload = dict(cast(dict[str, object], event["payload"]))
            try:
                await self.publisher.publish(
                    str(event["topic"]), str(event["message_key"]), payload
                )
            except BaseException:
                await self.repository.rollback()
                raise
            await self.repository.mark_published(str(event["id"]))
            count += 1
        return count
