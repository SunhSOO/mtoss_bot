from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


def _reject_non_finite(value: object, message: str) -> object:
    if isinstance(value, Decimal) and not value.is_finite():
        raise ValueError(message)
    return value


class RiskScope(StrEnum):
    SYSTEM = "SYSTEM"
    USER = "USER"
    ACCOUNT = "ACCOUNT"
    SOURCE = "SOURCE"
    SYMBOL = "SYMBOL"


class RiskMetric(StrEnum):
    ORDER_NOTIONAL = "ORDER_NOTIONAL"
    ACCOUNT_CAPITAL = "ACCOUNT_CAPITAL"
    SYMBOL_WEIGHT = "SYMBOL_WEIGHT"
    DAILY_LOSS = "DAILY_LOSS"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"


class RiskRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: UUID
    scope: RiskScope
    metric: RiskMetric
    limit: Decimal

    @field_validator("limit", mode="before")
    @classmethod
    def reject_float_limit(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("limit must not be a float")
        return _reject_non_finite(value, "limit must be finite")


class RiskContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_id: UUID
    order_notional: Decimal
    account_capital: Decimal
    resulting_symbol_weight: Decimal
    daily_loss: Decimal
    drawdown: Decimal

    @field_validator(
        "order_notional",
        "account_capital",
        "resulting_symbol_weight",
        "daily_loss",
        "drawdown",
        mode="before",
    )
    @classmethod
    def reject_float_metric(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("risk metrics must not be floats")
        return _reject_non_finite(value, "risk metrics must be finite")


class RiskViolation(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    metric: RiskMetric | None
    actual: Decimal | None
    limit: Decimal | None

    @field_validator("actual", "limit", mode="before")
    @classmethod
    def reject_float_values(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("risk values must not be floats")
        return _reject_non_finite(value, "risk values must be finite")


class RiskDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_id: UUID
    allowed: bool
    violations: tuple[RiskViolation, ...]
