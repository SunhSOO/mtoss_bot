"""봇에게 보낸 메시지에서 내 chat_id를 찾아낸다.

@userinfobot 같은 제3의 봇을 거칠 필요가 없다. 이미 내 봇에게 `/start`를 보냈다면
그 기록이 봇의 업데이트 큐에 남아 있고, 거기 발신자 id가 곧 chat_id다.

    uv run --env-file .env python ops/telegram_chat_id.py

`.env`에 `TELEGRAM_BOT_TOKEN`만 있으면 된다 (`TELEGRAM_CHAT_ID`는 아직 없어도 됨).

아무것도 안 나오면 텔레그램에서 내 봇 대화창을 열고 `/start`나 아무 메시지나 보낸 뒤
다시 실행하면 된다.
"""

import asyncio
import os
import sys
from typing import Any

import httpx2

API_ROOT = "https://api.telegram.org"


async def main() -> None:
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        sys.exit(
            ".env에 TELEGRAM_BOT_TOKEN이 없습니다.\n"
            "BotFather에서 받은 토큰을 먼저 넣으세요. TELEGRAM_CHAT_ID는 아직 없어도 됩니다."
        )

    async with httpx2.AsyncClient(timeout=httpx2.Timeout(20.0)) as client:
        me = await client.get(f"{API_ROOT}/bot{token}/getMe")
        if me.status_code == 401:
            sys.exit("토큰이 거부됐습니다(401). /revoke로 새로 받은 토큰이 맞는지 확인하세요.")
        me.raise_for_status()
        bot = me.json()["result"]
        print(f"봇 확인: @{bot['username']} ({bot['first_name']})\n")

        response = await client.get(f"{API_ROOT}/bot{token}/getUpdates", params={"limit": 100})
        response.raise_for_status()
        updates: list[dict[str, Any]] = response.json().get("result", [])

    senders: dict[int, str] = {}
    for update in updates:
        for key in ("message", "edited_message", "callback_query", "my_chat_member"):
            payload = update.get(key)
            if not isinstance(payload, dict):
                continue
            sender = payload.get("from")
            if not isinstance(sender, dict):
                continue
            sender_id = sender.get("id")
            if not isinstance(sender_id, int) or sender.get("is_bot"):
                continue
            name = " ".join(
                part for part in (sender.get("first_name"), sender.get("last_name")) if part
            )
            handle = f"@{sender['username']}" if sender.get("username") else "(사용자명 없음)"
            senders[sender_id] = f"{name} {handle}".strip()

    if not senders:
        sys.exit(
            "메시지 기록이 없습니다.\n\n"
            "텔레그램에서 내 봇 대화창을 열고 `/start`나 아무 메시지나 보낸 뒤 다시 실행하세요.\n"
            "이미 보내셨다면, 다른 프로그램이 먼저 업데이트를 가져갔을 수 있습니다 —\n"
            "메시지를 하나 더 보내고 다시 실행하면 됩니다."
        )

    print("이 봇에게 말을 건 사람:\n")
    for sender_id, label in senders.items():
        print(f"  TELEGRAM_CHAT_ID={sender_id}    {label}")

    if len(senders) == 1:
        only = next(iter(senders))
        print(f"\n.env에 이 줄을 추가하세요:\n\n  TELEGRAM_CHAT_ID={only}\n")
    else:
        print("\n여러 명이 잡혔습니다. 본인 것만 .env에 넣으세요.")


if __name__ == "__main__":
    asyncio.run(main())
