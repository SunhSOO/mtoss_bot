import json

import pytest
from redis.asyncio import Redis

from mtoss.infrastructure.queue.redis_streams import RedisStreamsPublisher


@pytest.mark.asyncio
async def test_redis_stream_contains_key_and_payload() -> None:
    redis = Redis.from_url("redis://localhost:6379/0")
    await redis.delete("test.execution")
    publisher = RedisStreamsPublisher(redis)

    await publisher.publish("test.execution", "k", {"intent_id": "i"})

    entries = await redis.xrange("test.execution")
    assert entries[0][1][b"message_key"] == b"k"
    assert json.loads(entries[0][1][b"payload"]) == {"intent_id": "i"}
    await redis.aclose()
