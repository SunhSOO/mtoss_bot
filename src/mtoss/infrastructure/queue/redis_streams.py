import json

from redis.asyncio import Redis


class RedisStreamsPublisher:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def publish(self, topic: str, key: str, payload: dict[str, object]) -> str:
        message_id = await self.redis.xadd(
            topic,
            {
                "message_key": key,
                "payload": json.dumps(payload, separators=(",", ":"), sort_keys=True),
            },
        )
        return message_id.decode() if isinstance(message_id, bytes) else str(message_id)
