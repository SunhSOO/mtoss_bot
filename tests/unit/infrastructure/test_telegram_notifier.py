import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from mtoss.domain.confirmations import ConfirmationChoice, ConfirmationRequest
from mtoss.domain.enums import OrderSide
from mtoss.infrastructure.notify.telegram import TelegramNotifier, render_confirmation

CHAT_ID = 12345
INTRUDER_ID = 99999


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeClient:
    """`post`만 흉내 내는 최소 클라이언트."""

    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.responses = responses or []
        self.fail_with: Exception | None = None

    async def post(self, url: str, json: dict[str, Any]) -> FakeResponse:
        self.calls.append((url, json))
        if self.fail_with is not None:
            raise self.fail_with
        payload = self.responses.pop(0) if self.responses else {"ok": True, "result": []}
        return FakeResponse(payload)

    async def aclose(self) -> None:
        return None


def build_request(confirmation_id: UUID | None = None) -> ConfirmationRequest:
    return ConfirmationRequest(
        confirmation_id=confirmation_id or uuid4(),
        symbol="XAUUSD",
        side=OrderSide.BUY,
        bar_close_time=datetime(2026, 8, 24, 12, 0, tzinfo=UTC),
        stop_price=Decimal("3960"),
        stop_distance=Decimal("45"),
        proposed_lots=Decimal("0.01"),
        risk_amount=Decimal("45"),
        budget=Decimal("38.96"),
        equity=Decimal("389.57"),
        deadline_at=datetime(2026, 8, 24, 12, 5, tzinfo=UTC),
    )


def notifier(client: FakeClient) -> TelegramNotifier:
    return TelegramNotifier("token", CHAT_ID, client=client)  # type: ignore[arg-type]


def callback_update(update_id: int, data: str, sender_id: int = CHAT_ID) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": "cb-1",
            "from": {"id": sender_id, "username": "someone"},
            "data": data,
        },
    }


def test_rendered_message_leads_with_the_numbers_that_matter() -> None:
    text = render_confirmation(build_request())

    assert "XAUUSD BUY" in text
    assert "45.00" in text  # 예상 손실
    assert "38.96" in text  # 리스크 예산
    assert "11.6%" in text  # 자본 대비 — 45 / 389.57
    assert "건너뜁니다" in text


def test_over_budget_excess_is_shown() -> None:
    request = build_request()
    assert request.over_budget_by == Decimal("6.04")
    assert "+6.04" in render_confirmation(request)


async def test_confirmation_request_carries_two_buttons() -> None:
    client = FakeClient()
    request = build_request()

    await notifier(client).request_confirmation(request)

    (url, payload) = client.calls[0]
    assert url.endswith("/sendMessage")
    assert payload["chat_id"] == CHAT_ID
    keyboard = json.loads(payload["reply_markup"])["inline_keyboard"][0]
    assert [button["callback_data"] for button in keyboard] == [
        f"enter:{request.confirmation_id}",
        f"skip:{request.confirmation_id}",
    ]


async def test_confirmation_request_surfaces_delivery_failure() -> None:
    """정보성 알림과 달리 확인 요청은 삼키지 않는다.

    배달됐는지 모르면서 답을 기다리는 건 의미가 없다.
    """
    client = FakeClient()
    client.fail_with = RuntimeError("network down")

    with pytest.raises(RuntimeError):
        await notifier(client).request_confirmation(build_request())


async def test_plain_notification_swallows_failures() -> None:
    client = FakeClient()
    client.fail_with = RuntimeError("network down")

    await notifier(client).notify("체결됨")  # 예외가 나가면 안 된다


async def test_enter_callback_is_parsed() -> None:
    request = build_request()
    client = FakeClient(
        [{"result": [callback_update(1, f"enter:{request.confirmation_id}")]}]
    )

    (response,) = await notifier(client).poll_responses()

    assert response.choice is ConfirmationChoice.ENTER
    assert response.confirmation_id == request.confirmation_id
    assert response.responder == str(CHAT_ID)


async def test_skip_callback_is_parsed() -> None:
    request = build_request()
    client = FakeClient([{"result": [callback_update(1, f"skip:{request.confirmation_id}")]}])

    (response,) = await notifier(client).poll_responses()
    assert response.choice is ConfirmationChoice.SKIP


async def test_callback_from_another_account_is_ignored() -> None:
    """이게 없으면 봇을 찾은 누구나 실계좌 진입 버튼을 누를 수 있다."""
    request = build_request()
    client = FakeClient(
        [{"result": [callback_update(1, f"enter:{request.confirmation_id}", INTRUDER_ID)]}]
    )

    assert await notifier(client).poll_responses() == ()


async def test_unparsable_callback_data_is_ignored() -> None:
    client = FakeClient([{"result": [callback_update(1, "enter:not-a-uuid")]}])
    assert await notifier(client).poll_responses() == ()


async def test_unknown_callback_prefix_is_ignored() -> None:
    client = FakeClient([{"result": [callback_update(1, f"delete:{uuid4()}")]}])
    assert await notifier(client).poll_responses() == ()


async def test_offset_advances_so_updates_are_not_replayed() -> None:
    request = build_request()
    client = FakeClient(
        [
            {"result": [callback_update(7, f"enter:{request.confirmation_id}")]},
            {"result": []},
        ]
    )
    telegram = notifier(client)

    await telegram.poll_responses()
    await telegram.poll_responses()

    (_, second_payload) = client.calls[1]
    assert second_payload["offset"] == 8


async def test_offset_advances_even_when_the_sender_is_rejected() -> None:
    """거부된 업데이트도 소비해야 한다. 안 그러면 같은 콜백을 영원히 다시 받는다."""
    client = FakeClient(
        [{"result": [callback_update(7, f"enter:{uuid4()}", INTRUDER_ID)]}, {"result": []}]
    )
    telegram = notifier(client)

    await telegram.poll_responses()
    await telegram.poll_responses()

    assert client.calls[1][1]["offset"] == 8


async def test_polling_failure_returns_nothing_instead_of_raising() -> None:
    client = FakeClient()
    client.fail_with = RuntimeError("timeout")

    assert await notifier(client).poll_responses() == ()


def test_expiry_is_decided_by_the_deadline() -> None:
    request = build_request()
    assert not request.is_expired(request.deadline_at - timedelta(seconds=1))
    assert request.is_expired(request.deadline_at)
