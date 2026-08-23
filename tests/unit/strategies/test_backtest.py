from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from mtoss.application.sizing import SymbolSpec
from mtoss.application.trade_manager import CloseReason, TrancheRole
from mtoss.domain.bars import Bar
from mtoss.domain.enums import OrderSide
from mtoss.strategies.ut_bot.backtest import (
    BacktestResult,
    FillKind,
    SkipReason,
    _Bracket,
    _bracket_exit,
    run_backtest,
)
from mtoss.strategies.ut_bot.config import UtBotConfig
from mtoss.strategies.ut_bot.signals import compute_signals
from tests.unit.strategies.test_signals import build_bars, v_shaped_closes

START = datetime(2026, 1, 1, tzinfo=UTC)
EQUITY = Decimal("389.57")

XAUUSD = SymbolSpec(
    symbol="XAUUSD",
    contract_size=Decimal("100"),
    volume_min=Decimal("0.01"),
    volume_step=Decimal("0.01"),
    volume_max=Decimal("100"),
)


def run(**overrides: Any) -> BacktestResult:
    confirm = bool(overrides.pop("confirm_over_budget", False))
    equity = overrides.pop("initial_equity", EQUITY)
    return run_backtest(
        build_bars(v_shaped_closes()),
        UtBotConfig(**overrides),
        initial_equity=equity,
        spec=XAUUSD,
        confirm_over_budget=confirm,
    )


def price_bar(*, open: str, high: str, low: str, close: str) -> Bar:
    return Bar(
        symbol="XAUUSD",
        timeframe="H1",
        open_time=START,
        open=Decimal(open),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
    )


def long_bracket(*, breakeven: bool = False, take_profit: str | None = "120") -> _Bracket:
    return _Bracket(
        role=TrancheRole.T1,
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        stop_loss=Decimal("100"),
        take_profit=None if take_profit is None else Decimal(take_profit),
        active_from=0,
        breakeven=breakeven,
    )


def test_stop_wins_when_both_levels_sit_inside_one_bar() -> None:
    # Pine의 최악 가정. 봉 내부 순서를 알 수 없으므로 손절이 먼저 걸린 것으로 본다.
    hit = _bracket_exit(long_bracket(), price_bar(open="110", high="125", low="95", close="120"))
    assert hit == (Decimal("100"), CloseReason.STOP_LOSS)


def test_stop_fills_at_the_open_when_price_gaps_through_it() -> None:
    hit = _bracket_exit(long_bracket(), price_bar(open="95", high="98", low="90", close="96"))
    assert hit == (Decimal("95"), CloseReason.STOP_LOSS)


def test_breakeven_stop_is_reported_separately() -> None:
    hit = _bracket_exit(
        long_bracket(breakeven=True), price_bar(open="105", high="108", low="95", close="99")
    )
    assert hit is not None
    assert hit[1] is CloseReason.BREAKEVEN_STOP


def test_target_fills_when_only_the_target_is_touched() -> None:
    hit = _bracket_exit(long_bracket(), price_bar(open="110", high="125", low="105", close="122"))
    assert hit == (Decimal("120"), CloseReason.TAKE_PROFIT)


def test_runner_without_a_target_only_exits_on_the_stop() -> None:
    bracket = long_bracket(take_profit=None)
    assert _bracket_exit(bracket, price_bar(open="110", high="200", low="105", close="190")) is None


def test_short_bracket_mirrors_the_long_case() -> None:
    bracket = _Bracket(
        role=TrancheRole.T1,
        side=OrderSide.SELL,
        quantity=Decimal("1"),
        stop_loss=Decimal("120"),
        take_profit=Decimal("100"),
        active_from=0,
        breakeven=False,
    )
    hit = _bracket_exit(bracket, price_bar(open="110", high="125", low="95", close="100"))
    assert hit == (Decimal("120"), CloseReason.STOP_LOSS)


def test_untouched_bracket_stays_open() -> None:
    quiet = price_bar(open="110", high="115", low="105", close="112")
    assert _bracket_exit(long_bracket(), quiet) is None


def test_backtest_produces_trades_on_a_reversal() -> None:
    assert run().trades


def test_entry_fills_on_the_bar_after_the_signal() -> None:
    bars = build_bars(v_shaped_closes())
    config = UtBotConfig()
    signals = compute_signals(bars, config)
    first_signal = next(item.index for item in signals if item.buy or item.sell)

    result = run()
    entries = [fill for fill in result.fills if fill.kind is FillKind.ENTRY]
    assert entries
    assert entries[0].bar_index == first_signal + 1
    assert entries[0].price == bars[first_signal + 1].open


def test_no_trade_opens_and_closes_on_the_same_bar() -> None:
    """진입 봉에는 브래킷이 아직 걸려 있지 않고, 청산도 다음 봉 시가에 나간다."""
    assert all(trade.exit_bar_index > trade.entry_bar_index for trade in run().trades)


def test_every_exit_is_paired_with_an_entry() -> None:
    result = run()
    entries = sum(1 for fill in result.fills if fill.kind is FillKind.ENTRY)
    exits = sum(1 for fill in result.fills if fill.kind is FillKind.EXIT)
    assert exits == len(result.trades)
    assert entries >= exits


def test_tranches_are_opened_in_pairs() -> None:
    entries = [fill for fill in run().fills if fill.kind is FillKind.ENTRY]
    per_bar: dict[int, set[TrancheRole]] = {}
    for fill in entries:
        per_bar.setdefault(fill.bar_index, set()).add(fill.role)
    assert all(roles == {TrancheRole.T1, TrancheRole.T2} for roles in per_bar.values())


def test_trade_points_are_signed_by_direction() -> None:
    for trade in run().trades:
        expected = (
            trade.exit_price - trade.entry_price
            if trade.side is OrderSide.BUY
            else trade.entry_price - trade.exit_price
        )
        assert trade.points == expected


def test_lot_cap_bounds_every_fill() -> None:
    """상한이 유일한 브레이크다. 0.01랏 × 100oz = 1 단위를 넘으면 안 된다."""
    result = run(max_lots=Decimal("0.01"))
    assert result.fills
    assert all(fill.quantity == Decimal("1") for fill in result.fills)


def test_equity_moves_with_realised_trades() -> None:
    result = run()
    realised = sum(
        (trade.points * trade.quantity for trade in result.trades), start=Decimal(0)
    )
    assert result.final_equity == result.initial_equity + realised


def test_drawdown_is_measured_from_the_peak() -> None:
    result = run()
    assert result.max_drawdown >= 0
    assert result.peak_equity >= result.initial_equity
    assert result.max_drawdown_pct >= 0


def test_over_budget_signals_are_skipped_when_nobody_answers() -> None:
    """무응답 = 건너뜀. 실운영 기본값과 같다."""
    result = run(risk_pct=Decimal("0.001"))

    assert not result.trades
    assert result.skips
    assert all(item.reason is SkipReason.AWAITING_CONFIRMATION for item in result.skips)
    assert result.final_equity == result.initial_equity


def test_confirming_over_budget_signals_lets_them_trade() -> None:
    skipped = run(risk_pct=Decimal("0.001"))
    confirmed = run(risk_pct=Decimal("0.001"), confirm_over_budget=True)

    assert not skipped.trades
    assert confirmed.trades
    assert not confirmed.skips


def test_confirmation_rate_reports_how_often_the_gate_fires() -> None:
    assert run(risk_pct=Decimal("0.001")).confirmation_rate == Decimal(100)
    assert run().confirmation_rate == Decimal(0)


def test_a_healthy_account_is_not_reported_as_ruined() -> None:
    assert run().ruined is False
