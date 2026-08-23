from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from mtoss.application.trade_manager import (
    ActionKind,
    CloseReason,
    TradeDecision,
    TradeState,
    TrancheRole,
    TrancheState,
    on_bar_close,
    on_entry_filled,
)
from mtoss.domain.bars import Bar
from mtoss.domain.enums import OrderSide
from mtoss.strategies.ut_bot.config import UtBotConfig
from mtoss.strategies.ut_bot.signals import BarSignal

START = datetime(2026, 1, 1, tzinfo=UTC)


def bar(index: int, *, high: str = "115", low: str = "105", close: str = "110") -> Bar:
    return Bar(
        symbol="XAUUSD",
        timeframe="H1",
        open_time=START + timedelta(hours=index),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
    )


def signal(index: int, **overrides: object) -> BarSignal:
    payload: dict[str, object] = {
        "index": index,
        "open_time": START + timedelta(hours=index),
        "buy": False,
        "sell": False,
        "hull_green": None,
        "hull_flip_down": False,
        "hull_flip_up": False,
        "trailing_stop": None,
        "stop_low": None,
        "stop_high": None,
    }
    payload.update(overrides)
    return BarSignal.model_validate(payload)


def buy_signal(config: UtBotConfig) -> TradeDecision:
    """4번 봉에 매수 신호가 나고 손절 기준이 100인 상태."""
    return on_bar_close(
        TradeState(), bar(4), signal(4, buy=True, stop_low=Decimal("100")), config
    )


def long_entry(config: UtBotConfig) -> TradeState:
    """진입 신호 → 다음 봉 시가 110 체결까지 진행된 상태를 만든다."""
    filled = on_entry_filled(buy_signal(config).state, Decimal("110"), 5, config)
    return filled.state


def test_buy_signal_queues_two_tranche_entries() -> None:
    config = UtBotConfig()
    decision = buy_signal(config)

    assert [action.kind for action in decision.actions] == [ActionKind.OPEN, ActionKind.OPEN]
    assert decision.state.side is OrderSide.BUY
    assert decision.state.pending_stop == Decimal("100")
    assert {item.role for item in decision.state.tranches} == {TrancheRole.T1, TrancheRole.T2}
    assert all(item.state is TrancheState.PENDING_ENTRY for item in decision.state.tranches)
    # 수량은 계좌 상태(자본·R)에 의존하므로 상태기계가 정하지 않는다. 워커가 채운다.
    assert all(item.quantity is None for item in decision.state.tranches)
    assert all(action.quantity is None for action in decision.actions)


def test_fill_stamps_the_sized_quantity_on_both_tranches() -> None:
    config = UtBotConfig()
    filled = on_entry_filled(
        buy_signal(config).state, Decimal("110"), 5, config, quantity=Decimal("2")
    )
    assert all(item.quantity == Decimal("2") for item in filled.state.tranches)


def test_aborted_entry_still_carries_the_quantity_on_close_actions() -> None:
    """중단되더라도 청산 동작에는 실제 체결 수량이 실려야 한다."""
    config = UtBotConfig()
    filled = on_entry_filled(
        buy_signal(config).state, Decimal("95"), 5, config, quantity=Decimal("2")
    )
    assert all(action.quantity == Decimal("2") for action in filled.actions)


def test_entry_without_a_stop_level_is_skipped_during_warmup() -> None:
    decision = on_bar_close(TradeState(), bar(2), signal(2, buy=True, stop_low=None), UtBotConfig())
    assert decision.actions == ()
    assert decision.state.is_flat


def test_fill_sets_one_to_one_target_on_t1_and_leaves_t2_running() -> None:
    config = UtBotConfig()
    state = long_entry(config)

    fixed = state.tranche(TrancheRole.T1)
    runner = state.tranche(TrancheRole.T2)
    assert fixed is not None and runner is not None
    assert fixed.stop_loss == Decimal("100")
    assert fixed.take_profit == Decimal("120")  # R = 10, rr_mult = 1.0
    assert runner.stop_loss == Decimal("100")
    assert runner.take_profit is None
    assert all(item.state is TrancheState.OPEN for item in state.tranches)


def test_fill_emits_bracket_actions_for_both_tranches() -> None:
    config = UtBotConfig()
    filled = on_entry_filled(buy_signal(config).state, Decimal("110"), 5, config)

    assert [action.kind for action in filled.actions] == [
        ActionKind.SET_BRACKETS,
        ActionKind.SET_BRACKETS,
    ]


def test_non_positive_risk_aborts_the_trade() -> None:
    config = UtBotConfig()
    # 갭으로 진입가가 손절가 아래에서 체결되면 R <= 0 이다.
    filled = on_entry_filled(buy_signal(config).state, Decimal("95"), 5, config)

    assert {action.reason for action in filled.actions} == {CloseReason.INVALID_RISK}
    assert filled.state.is_flat


def test_entry_gap_guard_rejects_a_far_open() -> None:
    config = UtBotConfig(max_entry_gap_bps=100)
    filled = on_entry_filled(
        buy_signal(config).state, Decimal("112"), 5, config, reference_close=Decimal("110")
    )
    assert {action.reason for action in filled.actions} == {CloseReason.ENTRY_GAP}
    assert filled.state.is_flat


def test_entry_gap_guard_allows_a_close_open() -> None:
    config = UtBotConfig(max_entry_gap_bps=100)
    filled = on_entry_filled(
        buy_signal(config).state, Decimal("110.5"), 5, config, reference_close=Decimal("110")
    )
    assert all(action.kind is ActionKind.SET_BRACKETS for action in filled.actions)


def test_breakeven_move_is_suppressed_on_the_entry_bar() -> None:
    config = UtBotConfig()
    state = long_entry(config)

    # 진입 봉(5)에서 익절가 120을 스쳐도 Pine의 `bar_index > entryBar` 때문에 옮기지 않는다.
    decision = on_bar_close(state, bar(5, high="125"), signal(5), config)
    runner = decision.state.tranche(TrancheRole.T2)
    assert runner is not None
    assert not runner.breakeven_moved
    assert decision.actions == ()


def test_breakeven_move_lifts_the_runner_stop_to_entry() -> None:
    config = UtBotConfig()
    state = long_entry(config)

    decision = on_bar_close(state, bar(6, high="121"), signal(6), config)

    assert [action.kind for action in decision.actions] == [ActionKind.MOVE_STOP]
    runner = decision.state.tranche(TrancheRole.T2)
    assert runner is not None
    assert runner.breakeven_moved
    assert runner.stop_loss == Decimal("110")


def test_breakeven_move_happens_only_once() -> None:
    config = UtBotConfig()
    state = on_bar_close(long_entry(config), bar(6, high="121"), signal(6), config).state
    decision = on_bar_close(state, bar(7, high="121"), signal(7), config)
    assert decision.actions == ()


def test_hull_flip_closes_only_the_runner() -> None:
    config = UtBotConfig()
    state = long_entry(config)

    decision = on_bar_close(state, bar(6), signal(6, hull_flip_down=True), config)

    assert [action.role for action in decision.actions] == [TrancheRole.T2]
    assert decision.actions[0].reason is CloseReason.HULL_FLIP
    fixed = decision.state.tranche(TrancheRole.T1)
    runner = decision.state.tranche(TrancheRole.T2)
    assert fixed is not None and runner is not None
    assert fixed.state is TrancheState.OPEN
    assert runner.state is TrancheState.CLOSED


def test_hull_exit_can_be_restricted_to_after_breakeven() -> None:
    config = UtBotConfig(only_after_be=True)
    state = long_entry(config)

    decision = on_bar_close(state, bar(6), signal(6, hull_flip_down=True), config)
    assert decision.actions == ()


def test_hull_exit_can_be_disabled() -> None:
    config = UtBotConfig(use_hull_exit=False)
    state = long_entry(config)

    decision = on_bar_close(state, bar(6), signal(6, hull_flip_down=True), config)
    assert decision.actions == ()


def test_opposite_signal_closes_everything_then_reverses() -> None:
    config = UtBotConfig()
    state = long_entry(config)

    decision = on_bar_close(state, bar(6), signal(6, sell=True, stop_high=Decimal("130")), config)

    kinds = [action.kind for action in decision.actions]
    assert kinds == [ActionKind.CLOSE, ActionKind.CLOSE, ActionKind.OPEN, ActionKind.OPEN]
    assert {action.reason for action in decision.actions[:2]} == {CloseReason.REVERSAL}
    assert decision.state.side is OrderSide.SELL
    assert decision.state.pending_stop == Decimal("130")
    assert all(item.state is TrancheState.PENDING_ENTRY for item in decision.state.tranches)


def test_same_side_signal_does_not_stack_a_second_position() -> None:
    config = UtBotConfig()
    state = long_entry(config)

    decision = on_bar_close(state, bar(6), signal(6, buy=True, stop_low=Decimal("100")), config)
    assert decision.actions == ()
    assert len(decision.state.tranches) == 2


def test_filling_without_a_pending_signal_is_rejected() -> None:
    with pytest.raises(ValueError, match="pending signal"):
        on_entry_filled(TradeState(), Decimal("110"), 5, UtBotConfig())
