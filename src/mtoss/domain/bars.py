from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from mtoss.domain.orders import validate_order_decimal_input


class Bar(BaseModel):
    """마감이 확정된 봉 하나. 형성 중인 봉은 이 모델로 만들지 않는다."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: str
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    tick_volume: int = 0
    spread: int = 0

    @field_validator("open_time")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("open_time must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("open", "high", "low", "close", mode="before")
    @classmethod
    def reject_float_price(cls, value: object) -> object:
        return validate_order_decimal_input(value, "bar price")

    @field_validator("open", "high", "low", "close")
    @classmethod
    def require_positive_price(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("bar prices must be positive")
        return value

    @field_validator("tick_volume", "spread")
    @classmethod
    def require_non_negative_counter(cls, value: int) -> int:
        if value < 0:
            raise ValueError("bar counters must be non-negative")
        return value

    @model_validator(mode="after")
    def require_consistent_range(self) -> "Bar":
        if self.high < self.low:
            raise ValueError("high must not be below low")
        if self.high < max(self.open, self.close):
            raise ValueError("high must cover open and close")
        if self.low > min(self.open, self.close):
            raise ValueError("low must cover open and close")
        return self
