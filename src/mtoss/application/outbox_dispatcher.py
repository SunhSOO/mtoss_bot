from typing import Protocol, cast

from mtoss.ports.event_publisher import EventPublisher


class OutboxRepositoryPort(Protocol):
    async def claim(self, limit: int) -> list[dict[str, object]]: ...

    async def mark_published(self, event_id: str) -> None: ...


class OutboxDispatcher:
    def __init__(self, repository: OutboxRepositoryPort, publisher: EventPublisher) -> None:
        self.repository = repository
        self.publisher = publisher

    async def dispatch_once(self, limit: int = 100) -> int:
        count = 0
        for event in await self.repository.claim(limit):
            payload = dict(cast(dict[str, object], event["payload"]))
            await self.publisher.publish(
                str(event["topic"]), str(event["message_key"]), payload
            )
            await self.repository.mark_published(str(event["id"]))
            count += 1
        return count
