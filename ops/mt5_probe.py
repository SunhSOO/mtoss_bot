"""MT5 계좌·심볼 스펙을 읽기만 하는 진단 스크립트.

주문을 내지 않는다. `order_check`는 순수 조회라 서버에 아무 흔적도 남기지 않는다.

이 스크립트가 답하는 것 — 전부 나머지 설계를 바꿀 수 있는 값들이다.

1. `margin_mode` — 헤징이어야 2트랜치(T1 고정익절 + T2 러너)가 성립한다. 넷팅이면
   심볼당 순포지션 1개·SL/TP 1쌍뿐이라 전략 구조 자체가 표현되지 않는다.
2. `trade_contract_size` — 100oz면 0.01랏 손절이 R달러, 10oz면 R/10달러다. 자본이
   작을수록 이 차이가 리스크% 사이징의 작동 여부를 가른다.
3. `volume_min`/`volume_step` — 0.01랏이 정말 최소인지.
4. `trade_stops_level` — 최소 스탑 거리. 크면 좁은 손절이 브로커에 거부된다.
5. `filling_mode` — FOK/IOC/RETURN 중 이 심볼이 받는 것.
6. 서버 시각 오프셋 — H1 봉 경계 판정 기준. MT5 시각은 UTC가 아니다.

실행:
    uv run --extra mt5 python ops/mt5_probe.py

이미 로그인된 MT5 터미널이 떠 있으면 자격증명 없이 그 세션에 붙는다. 따로 지정하려면
`MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` / `MT5_TERMINAL_PATH` 환경변수를 쓴다.
"""

import os
import sys
from datetime import UTC, datetime
from typing import Any

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - 진단 전용 스크립트
    sys.exit(
        "MetaTrader5 패키지가 없습니다. Windows에서 `uv sync --extra mt5`로 설치하세요."
    )

MARGIN_MODES = {
    0: "RETAIL_NETTING  ← 2트랜치 불가",
    1: "EXCHANGE",
    2: "RETAIL_HEDGING  ← 전략에 필요한 모드",
}

TRADE_MODES = {
    0: "DISABLED", 1: "LONGONLY", 2: "SHORTONLY", 3: "CLOSEONLY", 4: "FULL"
}

EXECUTION_MODES = {0: "REQUEST", 1: "INSTANT", 2: "MARKET", 3: "EXCHANGE"}


def decode_filling(mask: int, execution_mode: int) -> str:
    """`symbol_info.filling_mode`는 비트마스크다. FOK=1, IOC=2.

    RETURN은 마스크에 나타나지 않고 "시장 실행(MARKET)이 아니면 허용"이 규칙이다.
    """
    allowed = []
    if mask & 1:
        allowed.append("FOK")
    if mask & 2:
        allowed.append("IOC")
    if execution_mode != 2:
        allowed.append("RETURN")
    return ", ".join(allowed) if allowed else "(없음)"


def section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def show(label: str, value: object, note: str = "") -> None:
    suffix = f"   {note}" if note else ""
    print(f"  {label:<26} {value}{suffix}")


def connect() -> None:
    login = os.environ.get("MT5_LOGIN")
    kwargs: dict[str, Any] = {}
    path = os.environ.get("MT5_TERMINAL_PATH")
    if path:
        kwargs["path"] = path
    if login:
        kwargs["login"] = int(login)
        kwargs["password"] = os.environ.get("MT5_PASSWORD", "")
        kwargs["server"] = os.environ.get("MT5_SERVER", "")

    if not mt5.initialize(**kwargs):
        sys.exit(f"initialize 실패: {mt5.last_error()}")


def report_terminal() -> None:
    info = mt5.terminal_info()
    section("터미널")
    if info is None:
        show("terminal_info", f"None ({mt5.last_error()})")
        return
    show("connected", info.connected)
    show("trade_allowed", info.trade_allowed, "" if info.trade_allowed else "← 자동매매 꺼짐")
    show("path", info.path)
    show("data_path", info.data_path)


def report_account() -> int | None:
    account = mt5.account_info()
    section("계좌")
    if account is None:
        show("account_info", f"None ({mt5.last_error()})")
        return None

    show("login / server", f"{account.login} / {account.server}")
    show("currency", account.currency)
    show("balance / equity", f"{account.balance} / {account.equity}")
    show("margin_free", account.margin_free)
    show("leverage", f"1:{account.leverage}")
    show("margin_mode", MARGIN_MODES.get(account.margin_mode, account.margin_mode))
    show("fifo_close", account.fifo_close, "← True면 FIFO 청산 강제" if account.fifo_close else "")
    show("trade_allowed", account.trade_allowed)
    show("trade_expert", account.trade_expert)
    show("margin_so_call / so_so", f"{account.margin_so_call} / {account.margin_so_so}")
    return int(account.margin_mode)


def find_gold_symbols() -> list[str]:
    """XAUUSD 계열을 앞에 둔다. 알파벳순으로 자르면 정작 볼 심볼을 놓친다."""
    symbols = mt5.symbols_get()
    if symbols is None:
        return []
    names = sorted(item.name for item in symbols if "XAU" in item.name.upper())
    usd = [name for name in names if name.upper().startswith("XAUUSD")]
    rest = [name for name in names if not name.upper().startswith("XAUUSD")]
    return usd + rest


def report_symbol(name: str, equity: float, currency: str) -> None:
    if not mt5.symbol_select(name, True):
        show(name, f"symbol_select 실패 ({mt5.last_error()})")
        return

    info = mt5.symbol_info(name)
    tick = mt5.symbol_info_tick(name)
    if info is None or tick is None:
        show(name, f"정보 없음 ({mt5.last_error()})")
        return

    section(f"심볼: {name}")
    show("description", info.description)
    show("trade_contract_size", info.trade_contract_size, _contract_note(info.trade_contract_size))
    show("volume_min / step / max", f"{info.volume_min} / {info.volume_step} / {info.volume_max}")
    show("digits / point", f"{info.digits} / {info.point}")
    show("trade_stops_level", info.trade_stops_level, _stops_note(info))
    show("trade_freeze_level", info.trade_freeze_level)
    show("trade_mode", TRADE_MODES.get(info.trade_mode, info.trade_mode))
    show("trade_exemode", EXECUTION_MODES.get(info.trade_exemode, info.trade_exemode))
    filling = decode_filling(info.filling_mode, info.trade_exemode)
    show("filling_mode", f"{info.filling_mode} → {filling}")
    currencies = f"{info.currency_base} / {info.currency_profit} / {info.currency_margin}"
    show("base / profit / margin", currencies)
    show("bid / ask", f"{tick.bid} / {tick.ask}")
    show("spread (point)", info.spread)

    if info.currency_profit != currency:
        show("", "", f"⚠ 호가통화({info.currency_profit}) ≠ 계좌통화({currency}) — 환산 필요")

    report_risk_table(info, tick, equity)
    report_order_check(name, info, tick)


def _contract_note(size: float) -> str:
    if size == 100:
        return "← 0.01랏 = 1oz. 손절 시 손실 = R달러"
    if size == 10:
        return "← 0.01랏 = 0.1oz. 손실 = R/10 (사이징에 유리)"
    return ""


def _stops_note(info: Any) -> str:
    if info.trade_stops_level == 0:
        return "← 제한 없음"
    distance = info.trade_stops_level * info.point
    return f"← 최소 스탑 거리 {distance:.2f} ({info.currency_profit})"


def report_risk_table(info: Any, tick: Any, equity: float) -> None:
    """R별로 리스크% 사이징이 어떤 랏을 내는지 실제 스펙으로 계산한다."""
    print("\n  리스크% 사이징 (트랜치당 10%, 하한 0.01 / 상한 0.02)")
    budget = equity * 0.10
    print(f"    예산 = {equity:.2f} × 10% = {budget:.2f} {info.currency_profit}")
    print(f"    {'R':>8} {'계산 랏':>12} {'적용 랏':>10} {'2트랜치 손실':>14} {'자본 대비':>10}")
    for r in (10.0, 18.0, 25.0, 39.0, 45.0, 60.0):
        risk_per_lot = r * info.trade_contract_size
        raw = budget / risk_per_lot
        step = info.volume_step or 0.01
        clamped = max(min(raw, 0.02), info.volume_min)
        lots = int(clamped / step) * step
        loss = lots * risk_per_lot * 2
        flag = "  ← 확인 요청" if raw < info.volume_min else ""
        print(
            f"    {r:>8.2f} {raw:>12.4f} {lots:>10.2f} {loss:>14.2f} "
            f"{loss / equity * 100:>9.1f}%{flag}"
        )


def preferred_filling(info: Any) -> int:
    """심볼이 받는 필링 모드를 고른다.

    지정하지 않으면 MT5가 FOK를 기본으로 쓰는데, 이 브로커의 금 심볼은 IOC만 받아
    10030(Unsupported filling mode)이 난다. 어댑터도 반드시 이걸 골라 넣어야 한다.
    """
    if info.filling_mode & 2:
        return int(mt5.ORDER_FILLING_IOC)
    if info.filling_mode & 1:
        return int(mt5.ORDER_FILLING_FOK)
    return int(mt5.ORDER_FILLING_RETURN)


def report_order_check(name: str, info: Any, tick: Any) -> None:
    """주문을 내지 않고 증거금과 수용 여부만 확인한다."""
    print("\n  order_check (전송 없음)")
    if not tick.ask:
        print("    호가 없음 — 주말 휴장이면 정상. 장 열린 뒤 다시 확인할 것.")
        return
    for lots in (info.volume_min, 0.02):
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": name,
            "volume": float(lots),
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
            "deviation": 20,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": preferred_filling(info),
            "magic": 0,
        }
        result = mt5.order_check(request)
        if result is None:
            print(f"    {lots:>5} 랏 → None ({mt5.last_error()})")
            continue
        print(
            f"    {lots:>5} 랏 → retcode={result.retcode} margin={result.margin:.2f} "
            f"free_after={result.margin_free:.2f} level={result.margin_level:.1f}% "
            f"| {result.comment}"
        )


def report_server_time(name: str) -> None:
    tick = mt5.symbol_info_tick(name)
    section("서버 시각 오프셋")
    if tick is None:
        show("tick", f"None ({mt5.last_error()})")
        return
    if not tick.time:
        show("서버 시각", "없음", "← 휴장 중이면 정상. 장 열린 뒤 다시 확인할 것.")
        return
    server = datetime.fromtimestamp(tick.time, tz=UTC)
    now = datetime.now(UTC)
    offset_hours = (server - now).total_seconds() / 3600
    show("서버 시각(raw)", server.replace(tzinfo=None))
    show("현재 UTC", now.replace(tzinfo=None))
    show("오프셋", f"{offset_hours:+.1f} 시간", "← H1 봉 경계는 이 시각 기준")


def main() -> None:
    connect()
    try:
        report_terminal()
        margin_mode = report_account()
        account = mt5.account_info()
        equity = float(account.equity) if account else 0.0
        currency = account.currency if account else "USD"

        candidates = find_gold_symbols()
        section("금 관련 심볼")
        print("  " + (", ".join(candidates) if candidates else "(없음)"))

        wanted = [name for name in candidates if name.upper().startswith("XAUUSD")]
        for name in wanted or candidates[:3]:
            report_symbol(name, equity, currency)

        if candidates:
            report_server_time(candidates[0])

        section("판정")
        if margin_mode == 2:
            print("  ✓ 헤징 계좌 — 2트랜치 구조 그대로 구현 가능")
        elif margin_mode is not None:
            print("  ✗ 넷팅/거래소 계좌 — T1·T2가 서로 다른 손절을 동시에 가질 수 없다.")
            print("    헤징 계좌 개설을 먼저 검토할 것. 넷팅으로 가면 트랜치 에뮬레이션과")
            print("    로컬 스탑 감시가 필요하고, 서버가 꺼지면 손절이 사라진다.")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
