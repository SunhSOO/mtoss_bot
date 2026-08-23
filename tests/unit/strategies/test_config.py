from decimal import Decimal

import pytest
from pydantic import ValidationError

from mtoss.strategies.ut_bot.config import HullMode, SizingMode, UtBotConfig


def test_defaults_match_the_pine_inputs() -> None:
    config = UtBotConfig()
    assert config.symbol == "XAUUSD"
    assert config.timeframe == "H1"
    assert config.ut_key == Decimal("2.0")
    assert config.ut_atr == 6
    assert config.sl_len == 4
    assert config.rr_mult == Decimal("1.0")
    assert config.hull_mode is HullMode.HMA
    assert config.hull_len == 55


def test_sizing_defaults_match_the_live_account_decision() -> None:
    config = UtBotConfig()
    assert config.sizing_mode is SizingMode.RISK_PERCENT
    assert config.risk_pct == Decimal("0.10")
    assert config.base_lots == Decimal("0.01")
    assert config.max_lots == Decimal("0.02")
    assert config.confirmation_deadline_seconds == 300


def test_max_total_lots_doubles_the_cap() -> None:
    # 주문이 둘이므로 심볼에 실릴 수 있는 최대 총량은 상한의 두 배다.
    assert UtBotConfig(max_lots=Decimal("0.02")).max_total_lots == Decimal("0.04")


def test_hull_length_applies_the_multiplier_as_pine_does() -> None:
    assert UtBotConfig(hull_len=55, hull_mult=Decimal("1.0")).hull_length_effective == 55
    assert UtBotConfig(hull_len=55, hull_mult=Decimal("0.5")).hull_length_effective == 27
    # 0으로 잘려 지표가 터지지 않도록 최소 1을 보장한다.
    assert UtBotConfig(hull_len=1, hull_mult=Decimal("0.1")).hull_length_effective == 1


def test_warmup_covers_the_longest_indicator() -> None:
    config = UtBotConfig()
    assert config.warmup_bars > config.hull_length_effective


def test_float_settings_are_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be floats"):
        UtBotConfig(base_lots=0.01)  # type: ignore[arg-type]


def test_non_positive_lots_are_rejected() -> None:
    with pytest.raises(ValidationError, match="must be positive"):
        UtBotConfig(base_lots=Decimal("0"))


def test_cap_below_floor_is_rejected() -> None:
    with pytest.raises(ValidationError, match="max_lots must not be below base_lots"):
        UtBotConfig(base_lots=Decimal("0.05"), max_lots=Decimal("0.02"))


def test_absurd_risk_pct_is_rejected() -> None:
    # 트랜치가 둘이라 0.5는 이미 "한 트레이드에 계좌 전부"다.
    with pytest.raises(ValidationError, match="risks the whole account"):
        UtBotConfig(risk_pct=Decimal("0.6"))


def test_lengths_below_one_are_rejected() -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        UtBotConfig(ut_atr=0)


def test_confirmation_deadline_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        UtBotConfig(confirmation_deadline_seconds=0)


def test_gap_guard_must_be_positive_when_set() -> None:
    with pytest.raises(ValidationError, match="max_entry_gap_bps"):
        UtBotConfig(max_entry_gap_bps=0)
    assert UtBotConfig(max_entry_gap_bps=None).max_entry_gap_bps is None
