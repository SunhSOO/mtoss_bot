from decimal import Decimal
from typing import Any

import pytest

from mtoss.application.sizing import SizingOutcome, SizingRejection, SymbolSpec, size_entry
from mtoss.strategies.ut_bot.config import SizingMode, UtBotConfig

EQUITY = Decimal("389.57")
"""INFINOX 실계좌 자본. 계획서의 R별 표가 이 값 기준이다."""

XAUUSD = SymbolSpec(
    symbol="XAUUSD",
    contract_size=Decimal("100"),
    volume_min=Decimal("0.01"),
    volume_step=Decimal("0.01"),
    volume_max=Decimal("100"),
)


def size(stop_distance: str, **overrides: Any) -> SizingOutcome:
    return size_entry(
        config=UtBotConfig(**overrides),
        stop_distance=Decimal(stop_distance),
        spec=XAUUSD,
        equity=EQUITY,
    )


# 계획서의 산수 표를 그대로 옮긴 것이다.
# 예산 = 389.57 × 10% = 38.957, lots = 38.957 / (R × 100), 하한 0.01 / 상한 0.02, 0.01 스텝 내림.
@pytest.mark.parametrize(
    ("stop_distance", "expected_lots", "expected_risk", "confirm"),
    [
        ("10", "0.02", "20", False),
        ("18", "0.02", "36", False),
        ("25", "0.01", "25", False),
        ("38", "0.01", "38", False),
        ("40", "0.01", "40", True),
        ("60", "0.01", "60", True),
    ],
    ids=["상한", "상한-경계", "스텝-내림", "예산-안", "예산-초과", "이격-매우-큼"],
)
def test_risk_percent_table(
    stop_distance: str, expected_lots: str, expected_risk: str, confirm: bool
) -> None:
    outcome = size(stop_distance)
    assert outcome.lots == Decimal(expected_lots)
    assert outcome.risk_amount == Decimal(expected_risk)
    assert outcome.requires_confirmation is confirm


def test_budget_is_risk_pct_of_equity() -> None:
    assert size("25").budget == EQUITY * Decimal("0.10")


def test_confirmation_boundary_sits_where_min_lot_exactly_fits_the_budget() -> None:
    """예산 ÷ (R × 100)이 정확히 0.01이 되는 R이 경계다. 여기서는 $38.957."""
    exactly = size("38.957")
    just_over = size("38.958")

    assert exactly.requires_confirmation is False
    assert just_over.requires_confirmation is True


def test_quantity_is_base_units_not_lots() -> None:
    """0.02랏 × 100oz = 2oz. 랏을 그대로 넘기면 명목 한도가 무의미해진다."""
    outcome = size("10")
    assert outcome.lots == Decimal("0.02")
    assert outcome.quantity == Decimal("2")


def test_over_budget_by_reports_the_excess_for_the_alert() -> None:
    assert size("60").over_budget_by == Decimal("60") - EQUITY * Decimal("0.10")


def test_within_budget_reports_no_excess() -> None:
    assert size("25").over_budget_by == Decimal(0)


def test_cap_is_the_only_brake_when_the_stop_is_tight() -> None:
    """R이 작으면 계산 수량이 폭증한다. 레버리지 1:1000이면 브로커가 막지 않는다."""
    # 상한이 없었다면 0.38랏이 나왔을 것이다.
    assert Decimal("38.957") / Decimal("100") > Decimal("0.02")
    assert size("1").lots == Decimal("0.02")


def test_raising_the_cap_raises_the_size() -> None:
    assert size("10", max_lots=Decimal("0.05")).lots == Decimal("0.03")


def test_fixed_mode_ignores_the_stop_distance() -> None:
    tight = size("1", sizing_mode=SizingMode.FIXED)
    wide = size("500", sizing_mode=SizingMode.FIXED)

    assert tight.lots == wide.lots == Decimal("0.01")
    assert wide.requires_confirmation is False


def test_non_positive_stop_distance_is_rejected() -> None:
    outcome = size("0")
    assert outcome.lots is None
    assert outcome.rejection is SizingRejection.NON_POSITIVE_RISK


def test_broker_minimum_wins_over_a_smaller_base_lot() -> None:
    coarse = SymbolSpec(
        symbol="XAUUSD",
        contract_size=Decimal("100"),
        volume_min=Decimal("0.10"),
        volume_step=Decimal("0.10"),
        volume_max=Decimal("100"),
    )
    outcome = size_entry(
        config=UtBotConfig(), stop_distance=Decimal("10"), spec=coarse, equity=EQUITY
    )

    assert outcome.lots == Decimal("0.10")
    assert outcome.requires_confirmation is True


def test_volume_max_caps_the_size() -> None:
    tiny_max = SymbolSpec(
        symbol="XAUUSD",
        contract_size=Decimal("100"),
        volume_min=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        volume_max=Decimal("0.01"),
    )
    outcome = size_entry(
        config=UtBotConfig(), stop_distance=Decimal("10"), spec=tiny_max, equity=EQUITY
    )

    assert outcome.lots == Decimal("0.01")


def test_quote_currency_conversion_changes_the_money_risk() -> None:
    """계좌통화 ≠ 호가통화면 환산을 빠뜨렸을 때 금액 리스크가 통째로 틀린다."""
    unconverted = size("25")
    converted = size_entry(
        config=UtBotConfig(),
        stop_distance=Decimal("25"),
        spec=XAUUSD,
        equity=EQUITY,
        quote_to_account_rate=Decimal("0.5"),
    )

    assert converted.lots is not None and unconverted.lots is not None
    assert converted.lots > unconverted.lots


def test_larger_equity_allows_a_larger_size() -> None:
    small = size("40")
    large = size_entry(
        config=UtBotConfig(), stop_distance=Decimal("40"), spec=XAUUSD, equity=Decimal("10000")
    )

    assert small.requires_confirmation is True
    assert large.requires_confirmation is False
    assert large.lots == Decimal("0.02")
