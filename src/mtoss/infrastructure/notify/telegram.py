"""텔레그램 봇 어댑터.

**롱폴링(`getUpdates`)을 쓴다.** 웹훅은 인바운드 포트가 필요하지만 롱폴링은 아웃바운드
HTTPS만 쓴다. 미니PC에 열린 포트를 하나도 만들지 않는다는 원칙과 맞고, Cloudflare
Tunnel 구성과도 독립적이다.

**응답자는 `chat_id` 하나로 고정된다.** 이게 없으면 봇 이름을 알아낸 누구나 실계좌
진입 버튼을 누를 수 있다. 다른 id에서 온 콜백은 무시하고 기록만 남긴다.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx2
import structlog

from mtoss.domain.confirmations import (
    ConfirmationChoice,
    ConfirmationRequest,
    ConfirmationResponse,
    NotificationChannel,
)

logger = structlog.get_logger(__name__)

API_ROOT = "https://api.telegram.org"
CALLBACK_PREFIXES = {"enter": ConfirmationChoice.ENTER, "skip": ConfirmationChoice.SKIP}


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def render_confirmation(request: ConfirmationRequest) -> str:
    """사람이 3초 안에 판단할 수 있게 숫자를 앞에 둔다."""
    deadline = request.deadline_at.astimezone(UTC).strftime("%H:%M:%S UTC")
    return (
        f"⚠️ <b>예산 초과 신호</b>\n\n"
        f"<b>{request.symbol} {request.side.value}</b>\n"
        f"봉 마감  {request.bar_close_time.astimezone(UTC):%Y-%m-%d %H:%M} UTC\n\n"
        f"손절가       {request.stop_price}\n"
        f"이격(R)      {_money(request.stop_distance)}\n"
        f"수량         {request.proposed_lots} 랏 (최소 단위)\n\n"
        f"예상 손실    <b>{_money(request.risk_amount)}</b>\n"
        f"리스크 예산  {_money(request.budget)}\n"
        f"초과분       <b>+{_money(request.over_budget_by)}</b>\n"
        f"자본 대비    <b>{request.risk_pct_of_equity}%</b>  (자본 {_money(request.equity)})\n\n"
        f"수량을 더 줄일 수 없습니다. 답이 없으면 <b>{deadline}</b>에 건너뜁니다."
    )


class TelegramNotifier:
    def __init__(
        self,
        bot_token: str,
        chat_id: int,
        *,
        client: httpx2.AsyncClient | None = None,
        api_root: str = API_ROOT,
    ) -> None:
        self._token = bot_token
        self._chat_id = chat_id
        self._api_root = api_root
        self._client = client or httpx2.AsyncClient(timeout=httpx2.Timeout(35.0))
        self._offset: int | None = None

    def _url(self, method: str) -> str:
        return f"{self._api_root}/bot{self._token}/{method}"

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(self._url(method), json=payload)
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        return body

    async def notify(self, text: str) -> None:
        """정보성 알림. 실패가 매매를 막으면 안 되므로 삼키고 기록만 남긴다."""
        try:
            await self._post(
                "sendMessage",
                {"chat_id": self._chat_id, "text": text, "parse_mode": "HTML"},
            )
        except Exception:
            logger.exception("telegram_notify_failed")

    async def request_confirmation(self, request: ConfirmationRequest) -> None:
        """확인 요청은 삼키지 않는다 — 배달 실패를 모르면 답을 기다리는 의미가 없다."""
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": f"진입 ({request.proposed_lots}랏)",
                        "callback_data": f"enter:{request.confirmation_id}",
                    },
                    {
                        "text": "건너뛰기",
                        "callback_data": f"skip:{request.confirmation_id}",
                    },
                ]
            ]
        }
        await self._post(
            "sendMessage",
            {
                "chat_id": self._chat_id,
                "text": render_confirmation(request),
                "parse_mode": "HTML",
                "reply_markup": json.dumps(keyboard),
            },
        )

    async def poll_responses(
        self, timeout_seconds: int = 25
    ) -> tuple[ConfirmationResponse, ...]:
        payload: dict[str, Any] = {
            "timeout": timeout_seconds,
            "allowed_updates": ["callback_query"],
        }
        if self._offset is not None:
            payload["offset"] = self._offset

        try:
            body = await self._post("getUpdates", payload)
        except Exception:
            logger.exception("telegram_poll_failed")
            return ()

        responses: list[ConfirmationResponse] = []
        for update in body.get("result", []):
            self._offset = int(update["update_id"]) + 1
            parsed = self._parse_callback(update)
            if parsed is not None:
                responses.append(parsed)
        return tuple(responses)

    def _parse_callback(self, update: dict[str, Any]) -> ConfirmationResponse | None:
        query = update.get("callback_query")
        if not query:
            return None

        sender = query.get("from", {})
        sender_id = sender.get("id")
        if sender_id != self._chat_id:
            # 화이트리스트 밖. 조용히 버리지 않고 기록한다 — 남이 봇을 찾았다는 신호다.
            logger.warning(
                "telegram_callback_from_unknown_sender",
                sender_id=sender_id,
                username=sender.get("username"),
            )
            return None

        choice, confirmation_id = _split_callback_data(query.get("data", ""))
        if choice is None or confirmation_id is None:
            logger.warning("telegram_callback_unparsable", data=query.get("data"))
            return None

        return ConfirmationResponse(
            confirmation_id=confirmation_id,
            choice=choice,
            responder=str(sender_id),
            channel=NotificationChannel.TELEGRAM,
            received_at=datetime.now(UTC),
        )

    async def acknowledge(self, callback_query_id: str, text: str) -> None:
        """버튼의 로딩 표시를 없앤다. 실패해도 결정 자체에는 영향이 없다."""
        try:
            await self._post(
                "answerCallbackQuery",
                {"callback_query_id": callback_query_id, "text": text},
            )
        except Exception:
            logger.exception("telegram_acknowledge_failed")

    async def aclose(self) -> None:
        await self._client.aclose()


def _split_callback_data(data: str) -> tuple[ConfirmationChoice | None, UUID | None]:
    prefix, _, raw_id = data.partition(":")
    choice = CALLBACK_PREFIXES.get(prefix)
    if choice is None:
        return None, None
    try:
        return choice, UUID(raw_id)
    except ValueError:
        return None, None
