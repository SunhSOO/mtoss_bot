from datetime import UTC, datetime, timedelta
from decimal import Decimal

from mtoss.domain.bars import Bar
from mtoss.strategies.ut_bot.config import UtBotConfig
from mtoss.strategies.ut_bot.signals import compute_signals

START = datetime(2026, 1, 1, tzinfo=UTC)


def build_bars(closes: list[str]) -> list[Bar]:
    bars: list[Bar] = []
    for index, close in enumerate(closes):
        price = Decimal(close)
        bars.append(
            Bar(
                symbol="XAUUSD",
                timeframe="H1",
                open_time=START + timedelta(hours=index),
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
            )
        )
    return bars


def v_shaped_closes() -> list[str]:
    """완만한 하락 뒤 가파른 반등.

    상승 기울기가 ATR 밴드보다 완만하면 UT Bot은 매수 교차를 내지 않는다. 그게 이
    지표의 정상 동작이므로, 반등 구간은 밴드를 넘어설 만큼 가파르게 만든다.
    """
    down = [str(100 - index) for index in range(20)]
    up = [str(81 + index * 5) for index in range(1, 16)]
    return down + up


def test_no_signals_without_bars() -> None:
    assert compute_signals([], UtBotConfig()) == []


def test_trailing_stop_is_none_through_atr_warmup() -> None:
    config = UtBotConfig()
    signals = compute_signals(build_bars([str(100 + index) for index in range(20)]), config)

    warmup = signals[: config.ut_atr - 1]
    assert all(item.trailing_stop is None for item in warmup)
    assert signals[config.ut_atr - 1].trailing_stop is not None


def test_no_entry_signal_fires_during_warmup() -> None:
    config = UtBotConfig()
    signals = compute_signals(build_bars([str(100 + index) for index in range(20)]), config)

    warmup = signals[: config.ut_atr]
    assert not any(item.buy or item.sell for item in warmup)


def test_v_shape_produces_a_sell_then_a_buy() -> None:
    signals = compute_signals(build_bars(v_shaped_closes()), UtBotConfig())

    fired = [
        "SELL" if item.sell else "BUY" for item in signals if item.buy or item.sell
    ]
    assert fired, "V자 반전이면 신호가 나와야 한다"
    assert fired[0] == "SELL"
    assert "BUY" in fired


def test_signals_alternate_between_buy_and_sell() -> None:
    signals = compute_signals(build_bars(v_shaped_closes()), UtBotConfig())

    fired = ["SELL" if item.sell else "BUY" for item in signals if item.buy or item.sell]
    assert all(first != second for first, second in zip(fired, fired[1:], strict=False))


def test_buy_and_sell_never_fire_on_the_same_bar() -> None:
    signals = compute_signals(build_bars(v_shaped_closes()), UtBotConfig())
    assert not any(item.buy and item.sell for item in signals)


def test_stop_levels_track_the_lookback_window() -> None:
    config = UtBotConfig(sl_len=4)
    bars = build_bars(["100", "99", "98", "97", "96"])
    signals = compute_signals(bars, config)

    assert signals[2].stop_low is None
    # 마지막 4봉의 저가는 종가 - 1 이므로 96 봉 기준 최저는 96 - 1
    assert signals[4].stop_low == Decimal("95")
    assert signals[4].stop_high == Decimal("100")


def test_hull_flip_flags_are_mutually_exclusive() -> None:
    signals = compute_signals(build_bars(v_shaped_closes()), UtBotConfig())
    assert not any(item.hull_flip_up and item.hull_flip_down for item in signals)


def test_hull_stays_green_on_a_monotonic_rise() -> None:
    config = UtBotConfig(hull_len=8)
    signals = compute_signals(build_bars([str(100 + index) for index in range(40)]), config)

    coloured = [item.hull_green for item in signals if item.hull_green is not None]
    assert coloured
    assert all(coloured)
