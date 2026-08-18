from typing import Protocol


class EventPublisher(Protocol):
    async def publish(self, topic: str, key: str, payload: dict[str, object]) -> str: ...
