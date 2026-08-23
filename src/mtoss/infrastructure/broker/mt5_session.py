"""MT5 파이썬 API를 asyncio에서 안전하게 쓰기 위한 세션.

`MetaTrader5` 패키지는 **동기 함수 묶음이고 스레드 안전하지 않다.** 연결은
프로세스 전역 상태라, `initialize()`를 부른 스레드와 이후 호출 스레드가 달라지면
조용히 깨진다.

그래서 `max_workers=1` 전용 실행기 하나에 모든 호출을 몰아넣는다.
**`asyncio.to_thread`를 쓰면 안 된다** — 기본 실행기는 멀티스레드라 연속 호출이
서로 다른 스레드에 떨어진다.

호출이 타임아웃되면 그 스레드는 되살릴 수 없다(파이썬은 스레드를 죽이지 못한다).
in-process 복구를 시도하지 말고 세션을 `DEGRADED`로 표시한 뒤 **프로세스를
재시작**해야 한다.
"""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class SessionState(StrEnum):
    IDLE = "IDLE"
    READY = "READY"
    DEGRADED = "DEGRADED"
    """호출 스레드가 영구히 멈췄다. 프로세스를 재시작해야 한다."""

    CLOSED = "CLOSED"


class Mt5Unavailable(RuntimeError):
    pass


class Mt5Session:
    def __init__(
        self,
        client: Any,
        *,
        terminal_path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        call_timeout_seconds: float = 30.0,
    ) -> None:
        self._client = client
        self._terminal_path = terminal_path
        self._login = login
        self._password = password
        self._server = server
        self._call_timeout_seconds = call_timeout_seconds
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mt5")
        self._lock = asyncio.Lock()
        self.state = SessionState.IDLE

    async def start(self) -> None:
        """터미널에 붙는다. `initialize()`도 전용 스레드에서 돌아야 한다."""
        kwargs: dict[str, Any] = {}
        if self._terminal_path:
            kwargs["path"] = self._terminal_path
        if self._login is not None:
            kwargs["login"] = self._login
            kwargs["password"] = self._password or ""
            kwargs["server"] = self._server or ""

        ok = await self.call(lambda: self._client.initialize(**kwargs))
        if not ok:
            self.state = SessionState.DEGRADED
            raise Mt5Unavailable(f"initialize failed: {self._client.last_error()}")

        terminal = await self.call(self._client.terminal_info)
        account = await self.call(self._client.account_info)
        if terminal is None or account is None:
            self.state = SessionState.DEGRADED
            raise Mt5Unavailable("terminal or account info unavailable after initialize")
        if not terminal.trade_allowed:
            # 터미널에서 "알고리즘 거래 허용"이 꺼져 있으면 order_send가 전부 거부된다.
            # 조용히 진행하면 장중에야 알게 되므로 여기서 멈춘다.
            raise Mt5Unavailable(
                "terminal has automated trading disabled "
                "(Tools > Options > Expert Advisors)"
            )

        self.state = SessionState.READY
        logger.info(
            "mt5_session_ready",
            login=account.login,
            server=account.server,
            margin_mode=account.margin_mode,
            currency=account.currency,
        )

    async def call(self, operation: Callable[[], T]) -> T:
        """MT5 호출 하나를 전용 스레드에서 실행한다."""
        if self.state is SessionState.DEGRADED:
            raise Mt5Unavailable("session is degraded; restart the process")

        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(self._executor, operation),
                timeout=self._call_timeout_seconds,
            )
        except TimeoutError:
            # 스레드를 죽일 수 없으므로 이 세션은 끝난 것으로 본다.
            self.state = SessionState.DEGRADED
            logger.error("mt5_call_timed_out", timeout=self._call_timeout_seconds)
            raise

    async def exclusive(self) -> "asyncio.Lock":
        """`order_check → 선행기록 → order_send` 같은 묶음을 끼어들기 없이 돌린다."""
        return self._lock

    async def close(self) -> None:
        if self.state in (SessionState.READY, SessionState.DEGRADED):
            try:
                await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(
                        self._executor, self._client.shutdown
                    ),
                    timeout=self._call_timeout_seconds,
                )
            except Exception:
                logger.warning("mt5_shutdown_failed", exc_info=True)
        self._executor.shutdown(wait=False, cancel_futures=True)
        self.state = SessionState.CLOSED
