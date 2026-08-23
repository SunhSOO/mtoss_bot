from decimal import Decimal, DecimalException
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def _reject_float_or_non_finite(value: object) -> object:
    if isinstance(value, float):
        raise ValueError("strategy settings must not be floats")
    candidate: Decimal | None = None
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, str):
        try:
            candidate = Decimal(value)
        except DecimalException:
            return value
    if candidate is not None and not candidate.is_finite():
        raise ValueError("strategy settings must be finite")
    return value


class HullMode(StrEnum):
    HMA = "Hma"
    THMA = "Thma"
    EHMA = "Ehma"


class SizingMode(StrEnum):
    FIXED = "FIXED"
    """항상 `base_lots`. 리스크 게이트를 쓰지 않는다."""

    RISK_PERCENT = "RISK_PERCENT"
    """자본 대비 리스크%로 수량을 정하고, 하한 미만이면 확인을 요구한다."""


class UtBotConfig(BaseModel):
    """Pine 전략의 `input.*` 값 + 실거래용 수량 설정. 콘솔에서 이 스키마로 폼을 만든다.

    수량은 트랜치 하나 기준이다. 주문이 둘(T1, T2)이므로 심볼에 실리는 총량은 두 배다.
    """

    model_config = ConfigDict(frozen=True)

    symbol: str = "XAUUSD"
    timeframe: str = "H1"

    sizing_mode: SizingMode = SizingMode.RISK_PERCENT
    risk_pct: Decimal = Decimal("0.10")
    """트랜치당 허용 손실 비율. 두 트랜치가 함께 손절되면 이 값의 두 배를 잃는다."""

    base_lots: Decimal = Decimal("0.01")
    """하한이자 FIXED 모드의 수량. 브로커 `volume_min`보다 작으면 그쪽이 이긴다."""

    max_lots: Decimal = Decimal("0.02")
    """상한. 레버리지가 높으면 브로커가 막아 주지 않으므로 **이게 유일한 브레이크**다."""

    confirmation_deadline_seconds: int = 300
    """예산 초과 확인 요청의 응답 기한. 지나면 그 신호는 건너뛴다."""

    ut_key: Decimal = Decimal("2.0")
    ut_atr: int = 6

    sl_len: int = 4
    rr_mult: Decimal = Decimal("1.0")

    use_hull_exit: bool = True
    only_after_be: bool = False
    hull_mode: HullMode = HullMode.HMA
    hull_len: int = 55
    hull_mult: Decimal = Decimal("1.0")

    max_entry_gap_bps: int | None = None

    @field_validator(
        "risk_pct", "base_lots", "max_lots", "ut_key", "rr_mult", "hull_mult", mode="before"
    )
    @classmethod
    def reject_float_setting(cls, value: object) -> object:
        return _reject_float_or_non_finite(value)

    @field_validator("risk_pct", "base_lots", "max_lots", "ut_key", "rr_mult", "hull_mult")
    @classmethod
    def require_positive_setting(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("strategy settings must be positive")
        return value

    @field_validator("risk_pct")
    @classmethod
    def require_sane_risk(cls, value: Decimal) -> Decimal:
        # 1.0은 "한 트레이드에 계좌 전부"다. 트랜치가 둘이라 실제로는 그 두 배가 걸린다.
        if value > Decimal("0.5"):
            raise ValueError("risk_pct above 0.5 risks the whole account on one trade")
        return value

    @field_validator("ut_atr", "sl_len", "hull_len", "confirmation_deadline_seconds")
    @classmethod
    def require_positive_length(cls, value: int) -> int:
        if value < 1:
            raise ValueError("lengths must be at least 1")
        return value

    @model_validator(mode="after")
    def require_cap_above_floor(self) -> "UtBotConfig":
        if self.max_lots < self.base_lots:
            raise ValueError("max_lots must not be below base_lots")
        return self

    @field_validator("max_entry_gap_bps")
    @classmethod
    def require_positive_gap(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("max_entry_gap_bps must be positive when set")
        return value

    @property
    def hull_length_effective(self) -> int:
        """Pine `int(hullLen * hullMult)` — 0으로 잘리지 않도록 최소 1을 보장한다."""
        return max(int(self.hull_len * self.hull_mult), 1)

    @property
    def max_total_lots(self) -> Decimal:
        """T1 + T2가 동시에 최대일 때의 합계. 콘솔에 "최대 총 0.04랏"으로 보여 줄 값."""
        return self.max_lots * 2

    @property
    def warmup_bars(self) -> int:
        """신호가 나오기 전에 필요한 최소 봉 수. 스케줄러가 히스토리를 이만큼 받는다."""
        hull_span = self.hull_length_effective + 2
        return max(self.ut_atr, self.sl_len, hull_span) + 1
