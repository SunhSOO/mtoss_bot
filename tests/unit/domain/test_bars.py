from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from mtoss.domain.bars import Bar
from mtoss.domain.numeric import to_order_decimal

OPEN_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def build(**overrides: object) -> Bar:
    payload: dict[str, object] = {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "open_time": OPEN_TIME,
        "open": Decimal("4000"),
        "high": Decimal("4010"),
        "low": Decimal("3990"),
        "close": Decimal("4005"),
    }
    payload.update(overrides)
    return Bar.model_validate(payload)


def test_valid_bar_round_trips() -> None:
    bar = build()
    assert bar.close == Decimal("4005")
    assert bar.open_time == OPEN_TIME


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        build(open_time=datetime(2026, 1, 1))


def test_float_prices_are_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be a float"):
        build(close=4005.0)


def test_prices_beyond_database_scale_are_rejected() -> None:
    with pytest.raises(ValidationError, match="NUMERIC"):
        build(close=Decimal("4005.12345678901234"))


def test_non_positive_prices_are_rejected() -> None:
    with pytest.raises(ValidationError, match="must be positive"):
        build(low=Decimal("0"), open=Decimal("1"), close=Decimal("1"), high=Decimal("2"))


def test_high_must_cover_open_and_close() -> None:
    with pytest.raises(ValidationError, match="high must cover"):
        build(high=Decimal("4001"))


def test_low_must_cover_open_and_close() -> None:
    with pytest.raises(ValidationError, match="low must cover"):
        build(low=Decimal("4001"))


def test_negative_counters_are_rejected() -> None:
    with pytest.raises(ValidationError, match="non-negative"):
        build(spread=-1)


def test_to_order_decimal_fits_the_database_scale() -> None:
    # float를 그대로 Decimal에 넣으면 17자리 넘는 값이 나와 NUMERIC(28,10)을 넘긴다.
    value = to_order_decimal(4005.123456789012345)
    assert -value.as_tuple().exponent <= 10
    assert build(close=value).close == value


def test_to_order_decimal_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        to_order_decimal(float("nan"))
    with pytest.raises(ValueError, match="finite"):
        to_order_decimal(float("inf"))
