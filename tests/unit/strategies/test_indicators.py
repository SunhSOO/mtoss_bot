import math

import pytest

from mtoss.strategies.ut_bot.indicators import (
    atr,
    crossover,
    crossunder,
    ema,
    highest,
    hma,
    lowest,
    pine_round,
    rma,
    sma,
    true_range,
    wma,
)


def test_pine_round_breaks_ties_away_from_zero() -> None:
    # 파이썬 내장 round는 짝수로 붙여 2를 준다. Pine은 3이다.
    assert pine_round(2.5) == 3
    assert pine_round(0.5) == 1
    assert pine_round(-0.5) == -1
    assert pine_round(math.sqrt(55)) == 7


def test_sma_is_none_until_window_is_full() -> None:
    assert sma([1.0, 2.0, 3.0, 4.0], 2) == [None, 1.5, 2.5, 3.5]


def test_sma_propagates_na_inside_the_window() -> None:
    assert sma([1.0, None, 3.0, 4.0], 2) == [None, None, None, 3.5]


def test_rma_seeds_with_sma_then_uses_wilder_alpha() -> None:
    result = rma([1.0, 2.0, 3.0, 4.0], 2)
    assert result[0] is None
    assert result[1] == pytest.approx(1.5)
    # alpha = 1/2 이므로 0.5 * 3 + 0.5 * 1.5
    assert result[2] == pytest.approx(2.25)
    assert result[3] == pytest.approx(3.125)


def test_rma_differs_from_ema_at_the_same_length() -> None:
    values = [5.0, 7.0, 6.0, 9.0, 11.0, 8.0]
    assert rma(values, 3)[-1] != pytest.approx(ema(values, 3)[-1])


def test_ema_uses_two_over_length_plus_one() -> None:
    result = ema([1.0, 2.0, 3.0], 2)
    assert result[1] == pytest.approx(1.5)
    # alpha = 2/3
    assert result[2] == pytest.approx((2.0 / 3.0) * 3.0 + (1.0 / 3.0) * 1.5)


def test_wma_weights_the_current_bar_most() -> None:
    result = wma([1.0, 2.0, 3.0], 2)
    assert result[0] is None
    # 가중치는 현재 봉 4, 직전 봉 2, 합 6
    assert result[1] == pytest.approx((2.0 * 4 + 1.0 * 2) / 6)
    assert result[2] == pytest.approx((3.0 * 4 + 2.0 * 2) / 6)


def test_true_range_uses_bar_range_on_the_first_bar() -> None:
    highs = [10.0, 12.0]
    lows = [8.0, 11.0]
    closes = [9.0, 11.5]
    assert true_range(highs, lows, closes) == [2.0, 3.0]


def test_atr_is_rma_of_true_range() -> None:
    highs = [10.0, 12.0, 13.0, 11.0]
    lows = [8.0, 11.0, 12.0, 9.0]
    closes = [9.0, 11.5, 12.5, 10.0]
    assert atr(highs, lows, closes, 2) == rma(true_range(highs, lows, closes), 2)


def test_hma_is_none_through_warmup_then_tracks_a_rising_series() -> None:
    values = [float(index) for index in range(1, 41)]
    result = hma(values, 8)
    assert result[0] is None
    tail = [item for item in result if item is not None]
    assert tail == sorted(tail)


def test_lowest_and_highest_span_the_window_inclusive() -> None:
    values = [5.0, 3.0, 4.0, 7.0]
    assert lowest(values, 2) == [None, 3.0, 3.0, 4.0]
    assert highest(values, 2) == [None, 5.0, 4.0, 7.0]


def test_crossover_requires_previous_bar_at_or_below() -> None:
    assert crossover([1.0, 2.0, 3.0], [2.0, 2.0, 2.0]) == [False, False, True]


def test_crossunder_mirrors_crossover() -> None:
    assert crossunder([3.0, 2.0, 1.0], [2.0, 2.0, 2.0]) == [False, False, True]


def test_cross_is_false_when_either_series_is_na() -> None:
    assert crossover([None, 2.0, 3.0], [2.0, 2.0, 2.0])[1] is False
