"""텔레그램 설정이 실제로 동작하는지 끝까지 확인한다.

주문과는 아무 상관이 없다. 메시지를 보내고 버튼 응답을 받아 보는 것뿐이다.

    uv run --env-file .env python ops/telegram_check.py

세 가지를 순서대로 확인한다.

1. 봇이 나에게 메시지를 보낼 수 있는가 (토큰이 맞고, 내가 /start를 눌렀는가)
2. 버튼 달린 확인 요청이 도착하는가
3. 버튼을 누르면 그 응답이 여기까지 돌아오는가

3번까지 통과해야 "예산 초과 신호에 답한다"가 실제로 성립한다.
"""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from mtoss.config import Settings
from mtoss.domain.confirmations import ConfirmationChoice, ConfirmationRequest
from mtoss.domain.enums import OrderSide
from mtoss.infrastructure.notify.telegram import TelegramNotifier

WAIT_SECONDS = 120


def load_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as error:  # pragma: no cover - 진단 전용
        sys.exit(f"설정을 읽지 못했습니다: {error}")


async def main() -> None:
    settings = load_settings()

    if not settings.telegram_enabled:
        missing = []
        if settings.telegram_bot_token is None:
            missing.append("TELEGRAM_BOT_TOKEN")
        if settings.telegram_chat_id is None:
            missing.append("TELEGRAM_CHAT_ID")
        sys.exit(
            f"텔레그램이 꺼져 있습니다. .env에 다음이 없습니다: {', '.join(missing)}\n"
            "설정 방법은 docs/deployment/mini-pc.md 7절을 보세요."
        )

    assert settings.telegram_bot_token is not None
    assert settings.telegram_chat_id is not None

    notifier = TelegramNotifier(
        settings.telegram_bot_token.get_secret_value(), settings.telegram_chat_id
    )

    try:
        print(f"chat_id {settings.telegram_chat_id} 로 보냅니다.\n")

        print("1/3  일반 알림 전송…")
        await notifier.notify(
            "✅ <b>mtoss 연결 확인</b>\n토큰과 chat_id가 맞습니다."
        )
        print("     보냈습니다. 텔레그램에 도착했는지 확인하세요.\n")

        print("2/3  버튼 달린 확인 요청 전송…")
        request = ConfirmationRequest(
            confirmation_id=uuid4(),
            symbol="XAUUSD+",
            side=OrderSide.BUY,
            bar_close_time=datetime.now(UTC).replace(minute=0, second=0, microsecond=0),
            stop_price=Decimal("4560.00"),
            stop_distance=Decimal("45"),
            proposed_lots=Decimal("0.01"),
            risk_amount=Decimal("45"),
            budget=Decimal("38.96"),
            equity=Decimal("389.57"),
            deadline_at=datetime.now(UTC) + timedelta(seconds=WAIT_SECONDS),
        )
        # 실거래에서는 배달 실패를 삼키지 않는다. 여기서도 그대로 둔다.
        await notifier.request_confirmation(request)
        print("     보냈습니다. 이건 연습입니다 — 아무 버튼이나 누르세요.\n")

        print(f"3/3  응답 대기 (최대 {WAIT_SECONDS}초)…")
        deadline = datetime.now(UTC) + timedelta(seconds=WAIT_SECONDS)
        while datetime.now(UTC) < deadline:
            for response in await notifier.poll_responses(timeout_seconds=10):
                if response.confirmation_id != request.confirmation_id:
                    print(f"     (다른 확인 요청의 응답을 흘려보냄: {response.confirmation_id})")
                    continue
                label = "진입" if response.choice is ConfirmationChoice.ENTER else "건너뛰기"
                print(f"\n     받았습니다: {label}  (보낸 사람 {response.responder})")
                print("\n텔레그램 설정 완료. 신호 알림과 확인 응답이 전부 동작합니다.")
                return
        print(
            "\n     응답이 오지 않았습니다.\n"
            "     - 버튼을 눌렀는데도 안 왔다면 chat_id가 다를 수 있습니다.\n"
            "       봇이 아니라 @userinfobot 이 알려준 본인 id 여야 합니다.\n"
            "     - 실거래에서는 무응답이 '건너뛰기'로 처리됩니다."
        )
    finally:
        await notifier.aclose()


if __name__ == "__main__":
    asyncio.run(main())
