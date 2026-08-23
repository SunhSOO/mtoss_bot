"""리스크% 기반 수량 산정.

`수량 = (자본 × 리스크%) ÷ R`. 이격(R)이 크면 수량이 줄어 금액 리스크가 일정해진다.

**다만 최소 거래 단위가 이 조절을 제한한다.** XAUUSD 표준 계약 100oz에서 0.01랏은 1oz라
손절 시 손실이 곧 R달러다. 자본이 작으면 최소 랏조차 예산을 넘고, 그때는 더 줄일 방법이
없다. 그래서 `requires_confirmation`으로 올려 사람이 판단하게 한다 — 조용히 예산을
초과해 진입하지 않는다.

반대 방향도 있다. R이 작으면 계산 수량이 커진다. 레버리지가 높은 계좌에서는 브로커가
막아 주지 않으므로 `max_lots`가 사실상 유일한 브레이크다.
"""

from decimal import ROUND_FLOOR, Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from mtoss.strategies.ut_bot.config import SizingMode, UtBotConfig


class SizingRejection(StrEnum):
    BELOW_BROKER_MINIMUM = "BELOW_BROKER_MINIMUM"
    NON_POSITIVE_RISK = "NON_POSITIVE_RISK"


class SymbolSpec(BaseModel):
    """브로커에서 읽어 온 심볼 스펙. `mt5.symbol_info`가 원본이다."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    contract_size: Decimal
    volume_min: Decimal
    volume_step: Decimal
    volume_max: Decimal

    @field_validator("contract_size", "volume_min", "volume_step", "volume_max", mode="before")
    @classmethod
    def reject_float_spec(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("symbol spec values must not be floats")
        return value

    @field_validator("contract_size", "volume_min", "volume_step", "volume_max")
    @classmethod
    def require_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("symbol spec values must be positive")
        return value


class SizingOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    lots: Decimal | None
    """트랜치당 랏. `None`이면 진입 불가."""

    quantity: Decimal | None
    """`lots × contract_size` — 기준통화 단위. 랏이 아니다."""

    budget: Decimal
    """트랜치당 허용 손실액 (계좌통화)."""

    risk_amount: Decimal | None
    """이 수량으로 손절될 때 실제 잃는 금액 (계좌통화)."""

    requires_confirmation: bool
    rejection: SizingRejection | None = None

    @property
    def over_budget_by(self) -> Decimal:
        """예산 초과분. 확인 알림에 그대로 띄운다."""
        if self.risk_amount is None:
            return Decimal(0)
        return max(self.risk_amount - self.budget, Decimal(0))


def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    """랏은 항상 **내림**한다. 올리면 예산을 넘기게 된다."""
    multiples = (value / step).to_integral_value(rounding=ROUND_FLOOR)
    return (multiples * step).normalize()


def size_entry(
    *,
    config: UtBotConfig,
    stop_distance: Decimal,
    spec: SymbolSpec,
    equity: Decimal,
    quote_to_account_rate: Decimal = Decimal(1),
) -> SizingOutcome:
    """트랜치 하나에 넣을 수량을 정한다.

    `stop_distance`는 R — |진입가 − 손절가|를 호가통화로 표현한 값이다. 손절이
    `lowest(low, sl_len)`(신호봉 포함)이라 신호봉 마감에 이미 확정되지만, 실제 체결은
    다음 봉 시가이므로 **주문 제출 직전 호가로 다시 계산해 이 함수를 다시 호출**한다.

    `quote_to_account_rate`는 호가통화 → 계좌통화 환율이다. XAUUSD·USD 계좌면 1이지만,
    계좌통화가 다르면 반드시 넘겨야 한다. 빠뜨리면 금액 리스크가 통째로 틀린다.
    """
    budget = (equity * config.risk_pct).copy_abs()

    if stop_distance <= 0:
        return SizingOutcome(
            lots=None,
            quantity=None,
            budget=budget,
            risk_amount=None,
            requires_confirmation=False,
            rejection=SizingRejection.NON_POSITIVE_RISK,
        )

    risk_per_lot = stop_distance * spec.contract_size * quote_to_account_rate
    floor_lots = max(config.base_lots, spec.volume_min)

    if config.sizing_mode is SizingMode.FIXED:
        return _finalise(floor_lots, spec, budget, risk_per_lot, requires_confirmation=False)

    raw_lots = budget / risk_per_lot
    if raw_lots < floor_lots:
        # 최소 단위조차 예산을 넘는다. 더 줄일 수 없으므로 사람에게 올린다.
        return _finalise(floor_lots, spec, budget, risk_per_lot, requires_confirmation=True)

    capped = min(raw_lots, config.max_lots, spec.volume_max)
    return _finalise(capped, spec, budget, risk_per_lot, requires_confirmation=False)


def _finalise(
    lots: Decimal,
    spec: SymbolSpec,
    budget: Decimal,
    risk_per_lot: Decimal,
    *,
    requires_confirmation: bool,
) -> SizingOutcome:
    quantised = _floor_to_step(lots, spec.volume_step)
    if quantised < spec.volume_min:
        return SizingOutcome(
            lots=None,
            quantity=None,
            budget=budget,
            risk_amount=None,
            requires_confirmation=False,
            rejection=SizingRejection.BELOW_BROKER_MINIMUM,
        )
    return SizingOutcome(
        lots=quantised,
        quantity=(quantised * spec.contract_size).normalize(),
        budget=budget,
        risk_amount=quantised * risk_per_lot,
        requires_confirmation=requires_confirmation,
    )
