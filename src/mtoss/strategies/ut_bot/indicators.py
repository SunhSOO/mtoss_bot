"""TradingView Pine Script v6 지표를 그대로 옮긴 구현.

Pine은 내부적으로 float64로 계산한다. 여기서도 float를 쓰는 이유는 정확도를 포기해서가
아니라 **TradingView와 같은 값을 얻기 위해서**다. Decimal로 바꾸면 값이 더 정밀해지는
대신 마지막 자리가 달라져 교차(crossover) 판정이 뒤집힐 수 있고, 그러면 백테스트
정합성 검증 자체가 불가능해진다. 도메인 경계로 나가는 가격만
`mtoss.domain.numeric.to_order_decimal`로 환산한다.

`None`은 Pine의 `na`에 대응한다. 창(window) 안에 하나라도 `na`가 있으면 결과도 `na`다.
"""

import math
from collections.abc import Sequence

FloatSeries = Sequence[float | None]


def pine_round(value: float) -> int:
    """Pine `math.round` — 0.5는 0에서 멀어지는 쪽으로 올린다.

    파이썬 내장 `round`는 짝수 쪽으로 붙이는(banker's rounding) 방식이라 다르다.
    """
    if value >= 0:
        return int(math.floor(value + 0.5))
    return int(math.ceil(value - 0.5))


def sma(values: FloatSeries, length: int) -> list[float | None]:
    if length <= 0:
        raise ValueError("length must be positive")
    out: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < length:
            out.append(None)
            continue
        window = values[index + 1 - length : index + 1]
        if any(item is None for item in window):
            out.append(None)
            continue
        total = 0.0
        for item in window:
            assert item is not None
            total += item
        out.append(total / length)
    return out


def _recursive_average(values: FloatSeries, length: int, alpha: float) -> list[float | None]:
    """Pine의 `ta.ema`/`ta.rma` 공통 골격.

    첫 값은 SMA로 시딩하고 그 뒤로는 `alpha * src + (1 - alpha) * prev`를 쓴다.
    `na`를 만나면 결과도 `na`가 되고 **다음 봉에서 다시 SMA로 시딩**한다.
    Pine의 `na(sum[1]) ? ta.sma(...) : ...` 분기와 같은 동작이다.
    """
    seeded = sma(values, length)
    out: list[float | None] = []
    previous: float | None = None
    for index, value in enumerate(values):
        current: float | None
        if previous is None:
            current = seeded[index]
        elif value is None:
            current = None
        else:
            current = alpha * value + (1.0 - alpha) * previous
        out.append(current)
        previous = current
    return out


def rma(values: FloatSeries, length: int) -> list[float | None]:
    """Wilder 평활. `ta.atr`가 쓰는 평균이며 SMA·EMA와 다르다."""
    if length <= 0:
        raise ValueError("length must be positive")
    return _recursive_average(values, length, 1.0 / length)


def ema(values: FloatSeries, length: int) -> list[float | None]:
    if length <= 0:
        raise ValueError("length must be positive")
    return _recursive_average(values, length, 2.0 / (length + 1))


def wma(values: FloatSeries, length: int) -> list[float | None]:
    """Pine `ta.wma`. 가중치와 누적 순서까지 Pine 레퍼런스 구현을 따른다.

        norm = 0.0, sum = 0.0
        for i = 0 to length - 1
            weight = (length - i) * length
            norm += weight
            sum  += x[i] * weight

    `x[i]`는 i봉 전이므로 현재 봉이 가장 큰 가중치를 받는다.
    """
    if length <= 0:
        raise ValueError("length must be positive")
    out: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < length:
            out.append(None)
            continue
        norm = 0.0
        total = 0.0
        incomplete = False
        for offset in range(length):
            item = values[index - offset]
            if item is None:
                incomplete = True
                break
            weight = float((length - offset) * length)
            norm += weight
            total += item * weight
        out.append(None if incomplete else total / norm)
    return out


def true_range(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]
) -> list[float]:
    """Pine `ta.tr(true)` — 첫 봉은 이전 종가가 없으므로 high - low를 쓴다."""
    out: list[float] = []
    for index in range(len(highs)):
        if index == 0:
            out.append(highs[index] - lows[index])
            continue
        previous_close = closes[index - 1]
        out.append(
            max(
                highs[index] - lows[index],
                abs(highs[index] - previous_close),
                abs(lows[index] - previous_close),
            )
        )
    return out


def atr(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], length: int
) -> list[float | None]:
    return rma(true_range(highs, lows, closes), length)


def _double_minus_full(half: FloatSeries, full: FloatSeries) -> list[float | None]:
    out: list[float | None] = []
    for index in range(len(half)):
        a, b = half[index], full[index]
        out.append(None if a is None or b is None else 2.0 * a - b)
    return out


def hma(values: FloatSeries, length: int) -> list[float | None]:
    raw = _double_minus_full(wma(values, max(length // 2, 1)), wma(values, length))
    return wma(raw, max(pine_round(math.sqrt(length)), 1))


def ehma(values: FloatSeries, length: int) -> list[float | None]:
    raw = _double_minus_full(ema(values, max(length // 2, 1)), ema(values, length))
    return ema(raw, max(pine_round(math.sqrt(length)), 1))


def thma(values: FloatSeries, length: int) -> list[float | None]:
    third = wma(values, max(length // 3, 1))
    half = wma(values, max(length // 2, 1))
    full = wma(values, length)
    raw: list[float | None] = []
    for index in range(len(values)):
        a, b, c = third[index], half[index], full[index]
        raw.append(None if a is None or b is None or c is None else a * 3.0 - b - c)
    return wma(raw, length)


def lowest(values: Sequence[float], length: int) -> list[float | None]:
    if length <= 0:
        raise ValueError("length must be positive")
    return [
        None if index + 1 < length else min(values[index + 1 - length : index + 1])
        for index in range(len(values))
    ]


def highest(values: Sequence[float], length: int) -> list[float | None]:
    if length <= 0:
        raise ValueError("length must be positive")
    return [
        None if index + 1 < length else max(values[index + 1 - length : index + 1])
        for index in range(len(values))
    ]


def crossover(left: FloatSeries, right: FloatSeries) -> list[bool]:
    """Pine `ta.crossover` — 이번 봉에 위로 뚫고, 직전 봉에는 같거나 아래였다."""
    return _cross(left, right, upward=True)


def crossunder(left: FloatSeries, right: FloatSeries) -> list[bool]:
    return _cross(left, right, upward=False)


def _cross(left: FloatSeries, right: FloatSeries, *, upward: bool) -> list[bool]:
    out: list[bool] = []
    for index in range(len(left)):
        if index == 0:
            out.append(False)
            continue
        now_left, now_right = left[index], right[index]
        was_left, was_right = left[index - 1], right[index - 1]
        if None in (now_left, now_right, was_left, was_right):
            out.append(False)
            continue
        assert now_left is not None and now_right is not None
        assert was_left is not None and was_right is not None
        if upward:
            out.append(now_left > now_right and was_left <= was_right)
        else:
            out.append(now_left < now_right and was_left >= was_right)
    return out
