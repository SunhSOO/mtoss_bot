"""UT Bot 2-포지션 분할 전략의 포지션 수명주기 상태기계.

Pine 전략의 블록 1~6을 순수 함수로 옮긴 것이다. 브로커도 DB도 모르며, 입력은
(마감된 봉, 신호, 현재 상태)이고 출력은 (다음 상태, 실행할 동작 목록)이다. 덕분에
같은 코드가 백테스트 시뮬레이터와 실거래 워커 양쪽을 구동한다.

Pine과 의도적으로 다른 지점 두 가지(둘 다 더 안전한 쪽):

1. **SL/TP를 브로커에 붙인다.** Pine `strategy.exit`는 백테스터가 봉 내부에서
   판정하지만, 실거래에서 우리가 봉 마감에만 확인하면 H1 한 봉이 손절을 크게
   지나칠 수 있다. 브로커 측 스탑은 봉 내부에서 즉시 걸리고 서버가 꺼져 있어도
   작동한다. `SET_BRACKETS` 동작이 그 역할이다.
2. **`max_entry_gap_bps` 갭 방어.** Pine에는 없다. 주말·야간 휴장 갭으로 다음 봉
   시가가 신호봉 종가에서 크게 벌어지면 진입을 포기한다.

반대로 Pine에 충실하게 유지한 지점: 본절 이동은 **진입 봉에서는 일어나지 않는다**
(`bar_index > entryBar`). 진입 봉에서 익절가를 스쳤더라도 그 봉에서는 옮기지 않는다.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from mtoss.domain.bars import Bar
from mtoss.domain.enums import OrderSide
from mtoss.strategies.ut_bot.config import UtBotConfig
from mtoss.strategies.ut_bot.signals import BarSignal


class TrancheRole(StrEnum):
    T1 = "T1"
    """주문① — 고정 1:1 익절."""

    T2 = "T2"
    """주문② — 러너. 고정 익절 없음, 본절 이동과 Hull 반전 청산 대상."""


class TrancheState(StrEnum):
    PENDING_ENTRY = "PENDING_ENTRY"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class CloseReason(StrEnum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    BREAKEVEN_STOP = "BREAKEVEN_STOP"
    HULL_FLIP = "HULL_FLIP"
    REVERSAL = "REVERSAL"
    INVALID_RISK = "INVALID_RISK"
    ENTRY_GAP = "ENTRY_GAP"


class ActionKind(StrEnum):
    OPEN = "OPEN"
    """다음 봉 시가에 시장가 진입."""

    SET_BRACKETS = "SET_BRACKETS"
    """체결된 포지션에 SL/TP를 부착."""

    MOVE_STOP = "MOVE_STOP"
    """기존 포지션의 손절만 변경 (본절 이동)."""

    CLOSE = "CLOSE"
    """다음 봉 시가에 시장가 청산."""


class TradeAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: ActionKind
    role: TrancheRole
    side: OrderSide | None = None
    quantity: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    reason: CloseReason | None = None


class Tranche(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: TrancheRole
    side: OrderSide
    state: TrancheState
    quantity: Decimal | None = None
    """기준통화 단위. 체결 시 확정된다 — 수량은 계좌 상태에 의존하므로 상태기계가 정하지 않는다."""

    entry_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    entry_bar_index: int | None = None
    breakeven_moved: bool = False
    close_reason: CloseReason | None = None


class TradeState(BaseModel):
    """Pine의 `var` 블록에 해당한다. DB `strategy_tranches` 행으로 영속화된다."""

    model_config = ConfigDict(frozen=True)

    side: OrderSide | None = None
    pending_stop: Decimal | None = None
    reference_close: Decimal | None = None
    tranches: tuple[Tranche, ...] = ()

    def tranche(self, role: TrancheRole) -> Tranche | None:
        for item in self.tranches:
            if item.role is role:
                return item
        return None

    def live_tranches(self) -> tuple[Tranche, ...]:
        return tuple(item for item in self.tranches if item.state is not TrancheState.CLOSED)

    @property
    def is_flat(self) -> bool:
        return not self.live_tranches()


class TradeDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: TradeState
    actions: tuple[TradeAction, ...]


def _replace(state: TradeState, updated: Tranche) -> TradeState:
    tranches = tuple(updated if item.role is updated.role else item for item in state.tranches)
    return state.model_copy(update={"tranches": tranches})


def _touched(side: OrderSide, price: Decimal, bar: Bar) -> bool:
    """봉이 해당 가격을 건드렸는가. 롱은 고가로, 숏은 저가로 판정한다."""
    return bar.high >= price if side is OrderSide.BUY else bar.low <= price


def on_bar_close(
    state: TradeState, bar: Bar, signal: BarSignal, config: UtBotConfig
) -> TradeDecision:
    """봉 마감 시점의 판정. Pine 블록 2, 4, 5를 그 순서대로 수행한다."""
    actions: list[TradeAction] = []

    state, breakeven_actions = _apply_breakeven(state, bar, signal)
    actions.extend(breakeven_actions)

    state, hull_actions = _apply_hull_exit(state, signal, config)
    actions.extend(hull_actions)

    state, signal_actions = _apply_signal(state, bar, signal)
    actions.extend(signal_actions)

    return TradeDecision(state=state, actions=tuple(actions))


def _apply_breakeven(
    state: TradeState, bar: Bar, signal: BarSignal
) -> tuple[TradeState, list[TradeAction]]:
    """주문①의 익절가에 닿았으면 주문②의 손절을 진입가로 올린다 (Pine 블록 2)."""
    runner = state.tranche(TrancheRole.T2)
    fixed = state.tranche(TrancheRole.T1)
    if runner is None or fixed is None:
        return state, []
    if runner.state is not TrancheState.OPEN or runner.breakeven_moved:
        return state, []
    if fixed.take_profit is None or runner.entry_price is None:
        return state, []
    if runner.entry_bar_index is None or signal.index <= runner.entry_bar_index:
        # Pine의 `bar_index > entryBar`. 진입 봉에서는 옮기지 않는다.
        return state, []
    if not _touched(runner.side, fixed.take_profit, bar):
        return state, []

    moved = runner.model_copy(
        update={"stop_loss": runner.entry_price, "breakeven_moved": True}
    )
    action = TradeAction(
        kind=ActionKind.MOVE_STOP, role=TrancheRole.T2, stop_loss=runner.entry_price
    )
    return _replace(state, moved), [action]


def _apply_hull_exit(
    state: TradeState, signal: BarSignal, config: UtBotConfig
) -> tuple[TradeState, list[TradeAction]]:
    """Hull 밴드 색이 뒤집히면 러너만 청산한다 (Pine 블록 4)."""
    runner = state.tranche(TrancheRole.T2)
    if runner is None or runner.state is not TrancheState.OPEN:
        return state, []
    if not config.use_hull_exit:
        return state, []
    if config.only_after_be and not runner.breakeven_moved:
        return state, []

    flipped = signal.hull_flip_down if runner.side is OrderSide.BUY else signal.hull_flip_up
    if not flipped:
        return state, []

    closed = runner.model_copy(
        update={"state": TrancheState.CLOSED, "close_reason": CloseReason.HULL_FLIP}
    )
    action = TradeAction(
        kind=ActionKind.CLOSE,
        role=TrancheRole.T2,
        quantity=runner.quantity,
        reason=CloseReason.HULL_FLIP,
    )
    return _replace(state, closed), [action]


def _apply_signal(
    state: TradeState, bar: Bar, signal: BarSignal
) -> tuple[TradeState, list[TradeAction]]:
    """UT 신호 처리 — 반대 포지션 청산 후 같은 방향 2트랜치 진입 (Pine 블록 5)."""
    if signal.buy:
        side, pending_stop = OrderSide.BUY, signal.stop_low
    elif signal.sell:
        side, pending_stop = OrderSide.SELL, signal.stop_high
    else:
        return state, []

    actions: list[TradeAction] = []
    for tranche in state.live_tranches():
        if tranche.side is side:
            continue
        actions.append(
            TradeAction(
                kind=ActionKind.CLOSE,
                role=tranche.role,
                quantity=tranche.quantity,
                reason=CloseReason.REVERSAL,
            )
        )
        state = _replace(
            state,
            tranche.model_copy(
                update={"state": TrancheState.CLOSED, "close_reason": CloseReason.REVERSAL}
            ),
        )

    if not state.is_flat:
        # UT 신호는 구조상 Buy↔Sell로 교대하므로 여기 오면 같은 방향이 이미 살아 있다.
        # Pine의 `pyramiding = 2`가 추가 진입을 막는 것과 같은 결과로 둔다.
        return state, actions

    if pending_stop is None:
        # 손절 기준 봉이 아직 모자란 워밍업 구간. 진입하지 않는다.
        return state, actions

    entries = tuple(
        Tranche(role=role, side=side, state=TrancheState.PENDING_ENTRY)
        for role in (TrancheRole.T1, TrancheRole.T2)
    )
    # 수량은 비워 둔다. 워커가 `sizing.size_entry`로 채운 뒤 제출한다.
    actions.extend(
        TradeAction(kind=ActionKind.OPEN, role=tranche.role, side=side) for tranche in entries
    )
    opened = TradeState(
        side=side,
        pending_stop=pending_stop,
        reference_close=bar.close,
        tranches=entries,
    )
    return opened, actions


def on_entry_filled(
    state: TradeState,
    entry_price: Decimal,
    bar_index: int,
    config: UtBotConfig,
    quantity: Decimal | None = None,
    reference_close: Decimal | None = None,
) -> TradeDecision:
    """다음 봉 시가에 두 트랜치가 체결된 직후 호출한다 (Pine 블록 1).

    여기서 R = |진입가 − 손절가|이 확정되고 두 트랜치의 브래킷이 정해진다.
    R ≤ 0이면 (갭 등으로 진입가가 손절가보다 불리하면) 즉시 전량 청산한다.

    `quantity`는 실제로 체결된 트랜치당 수량(기준통화 단위)이다. 중단 시에도 청산
    동작이 올바른 수량을 싣도록 **어떤 판정보다 먼저** 트랜치에 기록한다.
    """
    side, stop_loss = state.side, state.pending_stop
    if side is None or stop_loss is None:
        raise ValueError("cannot fill an entry without a pending signal")

    pending = [item for item in state.tranches if item.state is TrancheState.PENDING_ENTRY]
    if not pending:
        raise ValueError("no tranche is awaiting entry")

    if quantity is not None:
        for tranche in pending:
            state = _replace(state, tranche.model_copy(update={"quantity": quantity}))
        pending = [item for item in state.tranches if item.state is TrancheState.PENDING_ENTRY]

    gap_reason = _entry_gap_reason(entry_price, reference_close, config)
    if gap_reason is not None:
        return _abort_entry(state, gap_reason)

    risk = entry_price - stop_loss if side is OrderSide.BUY else stop_loss - entry_price
    if risk <= 0:
        return _abort_entry(state, CloseReason.INVALID_RISK)

    target = (
        entry_price + config.rr_mult * risk
        if side is OrderSide.BUY
        else entry_price - config.rr_mult * risk
    )

    actions: list[TradeAction] = []
    updated = state
    for tranche in pending:
        take_profit = target if tranche.role is TrancheRole.T1 else None
        filled = tranche.model_copy(
            update={
                "state": TrancheState.OPEN,
                "entry_price": entry_price,
                "entry_bar_index": bar_index,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
            }
        )
        updated = _replace(updated, filled)
        actions.append(
            TradeAction(
                kind=ActionKind.SET_BRACKETS,
                role=tranche.role,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        )
    return TradeDecision(state=updated, actions=tuple(actions))


def _entry_gap_reason(
    entry_price: Decimal, reference_close: Decimal | None, config: UtBotConfig
) -> CloseReason | None:
    if config.max_entry_gap_bps is None or reference_close is None or reference_close <= 0:
        return None
    drift = abs(entry_price - reference_close) / reference_close * Decimal(10_000)
    return CloseReason.ENTRY_GAP if drift > config.max_entry_gap_bps else None


def _abort_entry(state: TradeState, reason: CloseReason) -> TradeDecision:
    actions: list[TradeAction] = []
    updated = state
    for tranche in state.live_tranches():
        actions.append(
            TradeAction(
                kind=ActionKind.CLOSE,
                role=tranche.role,
                quantity=tranche.quantity,
                reason=reason,
            )
        )
        closed = tranche.model_copy(
            update={"state": TrancheState.CLOSED, "close_reason": reason}
        )
        updated = _replace(updated, closed)
    return TradeDecision(state=flatten_if_done(updated), actions=tuple(actions))


def on_tranche_closed(
    state: TradeState, role: TrancheRole, reason: CloseReason
) -> TradeDecision:
    """브로커에서 트랜치가 실제로 닫혔음을 확인했을 때 상태를 정리한다."""
    tranche = state.tranche(role)
    if tranche is None or tranche.state is TrancheState.CLOSED:
        return TradeDecision(state=state, actions=())
    closed = tranche.model_copy(
        update={"state": TrancheState.CLOSED, "close_reason": reason}
    )
    return TradeDecision(state=flatten_if_done(_replace(state, closed)), actions=())


def flatten_if_done(state: TradeState) -> TradeState:
    """모든 트랜치가 닫혔으면 상태를 초기화한다 (Pine 블록 6)."""
    if not state.is_flat:
        return state
    return TradeState()
