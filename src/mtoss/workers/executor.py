"""아웃박스에 쌓인 실행 인텐트를 집어 실제로 브로커에 보내는 워커.

**이 파일이 없으면 주문은 절대 나가지 않는다.** 인텐트는 `QUEUED` 상태와
`execution.intent.ready` 아웃박스 행까지 만들어지고 거기서 멈춘다. 지금까지
`ExecutionService.execute()`를 호출하는 코드가 저장소에 하나도 없었다.

Redis를 쓰지 않는다. `outbox_events` 테이블 자체가 `FOR UPDATE SKIP LOCKED` 기반의
내구성 있는 큐라, 소비자가 한 박스 안에 하나뿐인 구성에서는 그걸로 충분하다.

전달 보장은 **최소 한 번**이다. 같은 인텐트가 두 번 실행될 수 있는데, 그건
`ExecutionService`가 먼저 `lock_for_execution`으로 상태를 보고 `QUEUED`가 아니면
그대로 반환하며, 브로커 어댑터도 멱등키로 재조회하기 때문에 안전하다.
"""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)

EXECUTION_TOPIC = "execution.intent.ready"

TERMINAL_ERRORS = (LookupError, PermissionError)
"""재시도해도 절대 성공하지 않는 오류.

- `LookupError`: 인텐트가 존재하지 않는다.
- `PermissionError`: 리스크·승인 증거가 없다.

이런 행을 놔두면 워커가 같은 실패를 무한 반복하며 CPU만 태운다. 소비 처리하되
경고를 남겨 사람이 보게 한다. 그 밖의 오류는 일시적일 수 있으므로 행을 남겨 둔다.
"""


class OutboxClaimPort(Protocol):
    async def claim(self, limit: int, topic: str | None = None) -> list[dict[str, object]]: ...

    async def mark_published(self, event_id: str) -> None: ...

    async def rollback(self) -> None: ...


class ExecutionWorker:
    def __init__(
        self,
        open_outbox: Callable[[], AbstractAsyncContextManager[OutboxClaimPort]],
        execute_intent: Callable[[UUID], Awaitable[object]],
        *,
        poll_interval_seconds: float = 1.0,
        error_backoff_seconds: float = 5.0,
    ) -> None:
        self._open_outbox = open_outbox
        self._execute_intent = execute_intent
        self._poll_interval_seconds = poll_interval_seconds
        self._error_backoff_seconds = error_backoff_seconds

    async def run_once(self, limit: int = 10) -> int:
        """준비된 인텐트를 최대 `limit`개 처리하고 처리 수를 돌려준다."""
        processed = 0
        while processed < limit:
            handled = await self._process_one()
            if not handled:
                break
            processed += 1
        return processed

    async def _process_one(self) -> bool:
        async with self._open_outbox() as outbox:
            events = await outbox.claim(1, EXECUTION_TOPIC)
            if not events:
                return False

            event = events[0]
            event_id = str(event["id"])
            intent_id = _read_intent_id(event)
            if intent_id is None:
                logger.error("execution_outbox_payload_unusable", event_id=event_id)
                await outbox.mark_published(event_id)
                return True

            try:
                await self._execute_intent(intent_id)
            except TERMINAL_ERRORS:
                # 재시도가 무의미하다. 소비하고 크게 기록한다.
                logger.exception(
                    "execution_intent_permanently_failed",
                    event_id=event_id,
                    intent_id=str(intent_id),
                )
                await outbox.mark_published(event_id)
                return True
            except Exception:
                # 일시적일 수 있다. 청구를 풀어 다음 순회에 다시 잡히게 한다.
                logger.exception(
                    "execution_intent_failed", event_id=event_id, intent_id=str(intent_id)
                )
                await outbox.rollback()
                raise

            await outbox.mark_published(event_id)
            logger.info("execution_intent_dispatched", intent_id=str(intent_id))
            return True

    async def run_forever(self, stop: asyncio.Event | None = None) -> None:
        stop = stop or asyncio.Event()
        while not stop.is_set():
            try:
                processed = await self.run_once()
            except Exception:
                # `_process_one`이 이미 기록했다. 여기서는 뜨겁게 도는 것만 막는다.
                await _sleep_until(stop, self._error_backoff_seconds)
                continue
            delay = 0.0 if processed else self._poll_interval_seconds
            if delay:
                await _sleep_until(stop, delay)


async def _sleep_until(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except TimeoutError:
        return


def _read_intent_id(event: dict[str, object]) -> UUID | None:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return None
    raw = payload.get("intent_id")
    if not isinstance(raw, str):
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None
