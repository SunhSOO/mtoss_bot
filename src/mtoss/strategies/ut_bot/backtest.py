"""Pine 전략 테스터의 주문 타이밍을 재현하는 시뮬레이터.

`trade_manager`의 상태기계를 그대로 쓰고, 다른 것은 **체결 시점 가정**뿐이다.

`process_orders_on_close = false`이므로 Pine에서 한 봉은 이렇게 처리된다.

1. 직전 봉 마감에 낸 시장가 주문이 이번 봉 **시가**에 체결된다.
2. 직전 봉까지 걸려 있던 스탑·리밋이 봉 내부에서 판정된다.
3. 스크립트가 봉 **마감**에 실행되어 다음 주문을 낸다.

따라서 진입 봉에는 아직 브래킷이 걸려 있지 않다. 실거래에서는 SL/TP를 브로커에 부착해
체결 즉시 보호되며, 이 차이는 항상 안전한 방향이다.

한 봉 안에서 손절과 익절이 모두 닿을 수 있으면 **손절이 먼저 체결된 것으로 본다.**
Pine의 최악 가정과 같다.

**자본을 추적한다.** 청산될 때마다 손익을 반영하고 다음 진입은 갱신된 자본으로 사이징한다.
이래야 "이 자본으로 이 전략이 살아남는가"에 답할 수 있다.
"""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from mtoss.application.sizing import SizingRejection, SymbolSpec, size_entry
from mtoss.application.trade_manager import (
    ActionKind,
    CloseReason,
    TradeAction,
    TradeState,
    TrancheRole,
    on_bar_close,
    on_entry_filled,
    on_tranche_closed,
)
from mtoss.domain.bars import Bar
from mtoss.domain.enums import OrderSide
from mtoss.strategies.ut_bot.config import UtBotConfig
from mtoss.strategies.ut_bot.signals import compute_signals


class FillKind(StrEnum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"


class SkipReason(StrEnum):
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    """R이 예산을 넘어 확인이 필요했고, 응답이 없어 건너뛴 신호."""

    BELOW_BROKER_MINIMUM = "BELOW_BROKER_MINIMUM"
    NON_POSITIVE_RISK = "NON_POSITIVE_RISK"
    ACCOUNT_RUINED = "ACCOUNT_RUINED"


class BacktestFill(BaseModel):
    model_config = ConfigDict(frozen=True)

    bar_index: int
    open_time: datetime
    kind: FillKind
    role: TrancheRole
    side: OrderSide
    price: Decimal
    quantity: Decimal
    reason: CloseReason | None = None


class BacktestSkip(BaseModel):
    """진입하지 않고 넘어간 신호. 확인 게이트가 얼마나 자주 걸리는지 보여 준다."""

    model_config = ConfigDict(frozen=True)

    bar_index: int
    open_time: datetime
    side: OrderSide
    reason: SkipReason
    stop_distance: Decimal
    budget: Decimal
    equity: Decimal


class BacktestTrade(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: TrancheRole
    side: OrderSide
    quantity: Decimal
    entry_bar_index: int
    entry_time: datetime
    entry_price: Decimal
    exit_bar_index: int
    exit_time: datetime
    exit_price: Decimal
    reason: CloseReason

    @property
    def points(self) -> Decimal:
        """부호 있는 가격 이동폭."""
        if self.side is OrderSide.BUY:
            return self.exit_price - self.entry_price
        return self.entry_price - self.exit_price


class BacktestResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    fills: tuple[BacktestFill, ...]
    trades: tuple[BacktestTrade, ...]
    skips: tuple[BacktestSkip, ...]
    final_state: TradeState
    initial_equity: Decimal
    final_equity: Decimal
    peak_equity: Decimal
    max_drawdown: Decimal
    """최고점 대비 최대 낙폭 (계좌통화)."""

    ruined: bool
    """자본이 0 이하로 떨어져 매매를 멈췄는가."""

    @property
    def max_drawdown_pct(self) -> Decimal:
        if self.peak_equity <= 0:
            return Decimal(0)
        return self.max_drawdown / self.peak_equity * 100

    @property
    def confirmation_rate(self) -> Decimal:
        """전체 진입 시도 중 확인 게이트에 걸린 비율(%)."""
        gated = sum(1 for item in self.skips if item.reason is SkipReason.AWAITING_CONFIRMATION)
        attempts = len({fill.bar_index for fill in self.fills}) + len(self.skips)
        if attempts == 0:
            return Decimal(0)
        return Decimal(gated) / Decimal(attempts) * 100


class _Bracket(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: TrancheRole
    side: OrderSide
    quantity: Decimal
    stop_loss: Decimal
    take_profit: Decimal | None
    active_from: int
    breakeven: bool


def _bracket_exit(bracket: _Bracket, bar: Bar) -> tuple[Decimal, CloseReason] | None:
    """이 봉에서 브래킷이 체결되었는지, 되었다면 가격과 사유를 돌려준다.

    갭으로 시가가 이미 레벨을 지나쳤으면 시가에 체결된 것으로 본다.
    """
    stop, target = bracket.stop_loss, bracket.take_profit
    if bracket.side is OrderSide.BUY:
        hit_stop = bar.low <= stop
        hit_target = target is not None and bar.high >= target
        stop_price = bar.open if bar.open <= stop else stop
        target_price = bar.open if target is not None and bar.open >= target else target
    else:
        hit_stop = bar.high >= stop
        hit_target = target is not None and bar.low <= target
        stop_price = bar.open if bar.open >= stop else stop
        target_price = bar.open if target is not None and bar.open <= target else target

    if hit_stop:
        reason = CloseReason.BREAKEVEN_STOP if bracket.breakeven else CloseReason.STOP_LOSS
        return stop_price, reason
    if hit_target and target_price is not None:
        return target_price, CloseReason.TAKE_PROFIT
    return None


def run_backtest(
    bars: Sequence[Bar],
    config: UtBotConfig,
    *,
    initial_equity: Decimal,
    spec: SymbolSpec,
    quote_to_account_rate: Decimal = Decimal(1),
    confirm_over_budget: bool = False,
) -> BacktestResult:
    """`confirm_over_budget=False`는 "예산 초과 신호에 답하지 않는다"는 뜻이다.

    실운영 기본값(무응답 = 건너뜀)과 같다. `True`로 두면 항상 확인해 주는 낙관적
    시나리오가 되며, 두 값을 비교하면 확인 게이트가 성과에 미치는 영향이 드러난다.
    """
    signals = compute_signals(bars, config)
    state = TradeState()
    brackets: dict[TrancheRole, _Bracket] = {}
    queued: list[TradeAction] = []
    fills: list[BacktestFill] = []
    skips: list[BacktestSkip] = []
    open_entries: dict[TrancheRole, BacktestFill] = {}
    trades: list[BacktestTrade] = []

    equity = initial_equity
    peak_equity = initial_equity
    max_drawdown = Decimal(0)
    ruined = False

    def record_exit(
        index: int, bar: Bar, role: TrancheRole, price: Decimal, reason: CloseReason
    ) -> None:
        nonlocal equity, peak_equity, max_drawdown, ruined
        entry = open_entries.pop(role, None)
        if entry is None:
            return
        fills.append(
            BacktestFill(
                bar_index=index,
                open_time=bar.open_time,
                kind=FillKind.EXIT,
                role=role,
                side=entry.side,
                price=price,
                quantity=entry.quantity,
                reason=reason,
            )
        )
        trade = BacktestTrade(
            role=role,
            side=entry.side,
            quantity=entry.quantity,
            entry_bar_index=entry.bar_index,
            entry_time=entry.open_time,
            entry_price=entry.price,
            exit_bar_index=index,
            exit_time=bar.open_time,
            exit_price=price,
            reason=reason,
        )
        trades.append(trade)
        equity += trade.points * trade.quantity * quote_to_account_rate
        peak_equity = max(peak_equity, equity)
        max_drawdown = max(max_drawdown, peak_equity - equity)
        if equity <= 0:
            ruined = True

    for index, bar in enumerate(bars):
        signal = signals[index]

        # 1) 직전 봉에서 예약한 시장가 주문을 이번 봉 시가에 체결한다.
        entered: list[TradeAction] = []
        for action in queued:
            if action.kind is ActionKind.CLOSE:
                # 상태기계가 이 동작을 낼 때 이미 트랜치를 CLOSED로 옮겼다. 여기서
                # `on_tranche_closed`를 다시 부르면, 반전 진입으로 같은 역할(T1/T2)에
                # 새로 생긴 트랜치를 닫아 버린다.
                brackets.pop(action.role, None)
                record_exit(
                    index, bar, action.role, bar.open, action.reason or CloseReason.REVERSAL
                )
            elif action.kind is ActionKind.OPEN:
                entered.append(action)
        queued = []

        quantity: Decimal | None = None
        if entered and state.side is not None and state.pending_stop is not None:
            stop_distance = abs(bar.open - state.pending_stop)
            skip = _skip_reason(
                config=config,
                stop_distance=stop_distance,
                spec=spec,
                equity=equity,
                rate=quote_to_account_rate,
                confirm_over_budget=confirm_over_budget,
                ruined=ruined,
            )
            if skip is not None:
                reason, budget = skip
                skips.append(
                    BacktestSkip(
                        bar_index=index,
                        open_time=bar.open_time,
                        side=state.side,
                        reason=reason,
                        stop_distance=stop_distance,
                        budget=budget,
                        equity=equity,
                    )
                )
                entered = []
                state = TradeState()
            else:
                outcome = size_entry(
                    config=config,
                    stop_distance=stop_distance,
                    spec=spec,
                    equity=equity,
                    quote_to_account_rate=quote_to_account_rate,
                )
                quantity = outcome.quantity

        for action in entered:
            assert action.side is not None and quantity is not None
            fill = BacktestFill(
                bar_index=index,
                open_time=bar.open_time,
                kind=FillKind.ENTRY,
                role=action.role,
                side=action.side,
                price=bar.open,
                quantity=quantity,
            )
            fills.append(fill)
            open_entries[action.role] = fill

        # 2) 이전 봉까지 활성화된 브래킷을 봉 내부에서 판정한다.
        for role in list(brackets):
            bracket = brackets[role]
            if bracket.active_from > index:
                continue
            hit = _bracket_exit(bracket, bar)
            if hit is None:
                continue
            price, close_reason = hit
            del brackets[role]
            record_exit(index, bar, role, price, close_reason)
            state = on_tranche_closed(state, role, close_reason).state

        # 3) 봉 마감에 스크립트를 실행한다. 진입 확정이 먼저(Pine 블록 1).
        if entered:
            decision = on_entry_filled(
                state,
                bar.open,
                index,
                config,
                quantity=quantity,
                reference_close=state.reference_close,
            )
            state = decision.state
            queued.extend(_register_brackets(decision.actions, state, brackets, index))

        decision = on_bar_close(state, bar, signal, config)
        state = decision.state
        queued.extend(_register_brackets(decision.actions, state, brackets, index))

    return BacktestResult(
        fills=tuple(fills),
        trades=tuple(trades),
        skips=tuple(skips),
        final_state=state,
        initial_equity=initial_equity,
        final_equity=equity,
        peak_equity=peak_equity,
        max_drawdown=max_drawdown,
        ruined=ruined,
    )


def _skip_reason(
    *,
    config: UtBotConfig,
    stop_distance: Decimal,
    spec: SymbolSpec,
    equity: Decimal,
    rate: Decimal,
    confirm_over_budget: bool,
    ruined: bool,
) -> tuple[SkipReason, Decimal] | None:
    """진입을 포기해야 하면 (사유, 예산)을 돌려준다."""
    budget = equity * config.risk_pct
    if ruined or equity <= 0:
        return SkipReason.ACCOUNT_RUINED, budget

    outcome = size_entry(
        config=config,
        stop_distance=stop_distance,
        spec=spec,
        equity=equity,
        quote_to_account_rate=rate,
    )
    if outcome.rejection is SizingRejection.NON_POSITIVE_RISK:
        return SkipReason.NON_POSITIVE_RISK, outcome.budget
    if outcome.rejection is SizingRejection.BELOW_BROKER_MINIMUM or outcome.lots is None:
        return SkipReason.BELOW_BROKER_MINIMUM, outcome.budget
    if outcome.requires_confirmation and not confirm_over_budget:
        return SkipReason.AWAITING_CONFIRMATION, outcome.budget
    return None


def _register_brackets(
    actions: Sequence[TradeAction],
    state: TradeState,
    brackets: dict[TrancheRole, _Bracket],
    index: int,
) -> list[TradeAction]:
    """브래킷 설정·이동은 즉시 반영하고, 시장가 주문만 다음 봉으로 넘긴다."""
    deferred: list[TradeAction] = []
    for action in actions:
        if action.kind is ActionKind.SET_BRACKETS:
            tranche = state.tranche(action.role)
            if tranche is None or action.stop_loss is None or tranche.quantity is None:
                continue
            brackets[action.role] = _Bracket(
                role=action.role,
                side=tranche.side,
                quantity=tranche.quantity,
                stop_loss=action.stop_loss,
                take_profit=action.take_profit,
                active_from=index + 1,
                breakeven=False,
            )
        elif action.kind is ActionKind.MOVE_STOP:
            existing = brackets.get(action.role)
            if existing is None or action.stop_loss is None:
                continue
            brackets[action.role] = existing.model_copy(
                update={
                    "stop_loss": action.stop_loss,
                    "breakeven": True,
                    "active_from": index + 1,
                }
            )
        else:
            if action.kind is ActionKind.CLOSE:
                brackets.pop(action.role, None)
            deferred.append(action)
    return deferred
