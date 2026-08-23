"""UT Bot 트레일링 스탑과 Hull 밴드 색을 봉 단위 신호로 계산한다.

여기는 **신호만** 만든다. 포지션 수명주기(트랜치 열기/닫기, 본절 이동)는
`mtoss.application.trade_manager`가 소유한다. 이렇게 나눠야 전략 코드가 브로커를
전혀 모르게 유지되고(설계서 §3), 상태기계를 따로 검증할 수 있다.
"""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from mtoss.domain.bars import Bar
from mtoss.domain.numeric import to_order_decimal
from mtoss.strategies.ut_bot.config import HullMode, UtBotConfig
from mtoss.strategies.ut_bot.indicators import (
    atr,
    crossover,
    crossunder,
    ehma,
    highest,
    hma,
    lowest,
    thma,
)


class BarSignal(BaseModel):
    """마감된 봉 하나에 대한 신호 스냅샷."""

    model_config = ConfigDict(frozen=True)

    index: int
    open_time: datetime
    buy: bool
    sell: bool
    hull_green: bool | None
    hull_flip_down: bool
    hull_flip_up: bool
    trailing_stop: Decimal | None
    stop_low: Decimal | None
    stop_high: Decimal | None


def _trailing_stop(closes: Sequence[float], nloss: Sequence[float | None]) -> list[float | None]:
    """Pine 원본의 3항 연쇄를 그대로 옮긴다.

        var float ts = 0.0
        ts := close > nz(ts[1],0) and close[1] > nz(ts[1],0) ? max(nz(ts[1]), close - nLoss) :
              close < nz(ts[1],0) and close[1] < nz(ts[1],0) ? min(nz(ts[1]), close + nLoss) :
              close > nz(ts[1],0) ? close - nLoss : close + nLoss

    **초기값 0.0이 중요하다.** ATR 워밍업이 끝나기 전에는 `nLoss`가 `na`라 `ts`도 `na`가
    되고, 첫 유효 봉에서 기준선이 0에서 출발한다. 이 워밍업 궤적을 그대로 재현하지
    않으면 이후 트레일링 스탑이 통째로 어긋난다.
    """
    out: list[float | None] = []
    previous: float | None = None
    for index, close in enumerate(closes):
        base = 0.0 if previous is None else previous
        loss = nloss[index]
        current: float | None
        if loss is None:
            current = None
        else:
            previous_close = closes[index - 1] if index > 0 else None
            if close > base and previous_close is not None and previous_close > base:
                current = max(base, close - loss)
            elif close < base and previous_close is not None and previous_close < base:
                current = min(base, close + loss)
            elif close > base:
                current = close - loss
            else:
                current = close + loss
        out.append(current)
        previous = current
    return out


def _hull(closes: Sequence[float], config: UtBotConfig) -> list[float | None]:
    length = config.hull_length_effective
    if config.hull_mode is HullMode.HMA:
        return hma(closes, length)
    if config.hull_mode is HullMode.EHMA:
        return ehma(closes, length)
    # Pine은 `f_thma(close, hullLenEff / 2)`로 호출한다. 정수 나눗셈임에 유의.
    return thma(closes, max(length // 2, 1))


def _hull_colors(hull: Sequence[float | None]) -> list[bool | None]:
    """`hullGreen = hull > hull[2]` — 직전 봉이 아니라 **2봉 전**과 비교한다."""
    colors: list[bool | None] = []
    for index in range(len(hull)):
        current = hull[index]
        earlier = hull[index - 2] if index >= 2 else None
        colors.append(None if current is None or earlier is None else current > earlier)
    return colors


def compute_signals(bars: Sequence[Bar], config: UtBotConfig) -> list[BarSignal]:
    """마감된 봉들에 대한 신호 계열을 만든다.

    `bars`는 시간 오름차순이며 **형성 중인 봉을 포함하면 안 된다.** MT5의
    `copy_rates_from_pos(..., 0, n)`은 index 0이 형성 중인 봉이므로 호출부에서 잘라낸다.
    """
    if not bars:
        return []

    closes = [float(bar.close) for bar in bars]
    highs = [float(bar.high) for bar in bars]
    lows = [float(bar.low) for bar in bars]

    key = float(config.ut_key)
    average_range = atr(highs, lows, closes, config.ut_atr)
    nloss = [None if value is None else key * value for value in average_range]

    trailing = _trailing_stop(closes, nloss)
    buys = crossover(closes, trailing)
    sells = crossunder(closes, trailing)

    colors = _hull_colors(_hull(closes, config))
    stop_lows = lowest(lows, config.sl_len)
    stop_highs = highest(highs, config.sl_len)

    signals: list[BarSignal] = []
    for index, bar in enumerate(bars):
        previous_color = colors[index - 1] if index > 0 else None
        color = colors[index]
        signals.append(
            BarSignal(
                index=index,
                open_time=bar.open_time,
                buy=buys[index],
                sell=sells[index],
                hull_green=color,
                hull_flip_down=color is False and previous_color is True,
                hull_flip_up=color is True and previous_color is False,
                trailing_stop=_optional_decimal(trailing[index]),
                stop_low=_optional_decimal(stop_lows[index]),
                stop_high=_optional_decimal(stop_highs[index]),
            )
        )
    return signals


def _optional_decimal(value: float | None) -> Decimal | None:
    return None if value is None else to_order_decimal(value)
