from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ApprovalMode(StrEnum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    CONDITIONAL = "CONDITIONAL"


class ApprovalStatus(StrEnum):
    APPROVED = "APPROVED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ApprovalPolicyConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    mode: ApprovalMode
    auto_notional_limit: Decimal | None

    @field_validator("auto_notional_limit", mode="before")
    @classmethod
    def reject_invalid_limit(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("auto_notional_limit must not be a float")
        if isinstance(value, Decimal) and not value.is_finite():
            raise ValueError("auto_notional_limit must be finite")
        return value

    @field_validator("auto_notional_limit")
    @classmethod
    def require_finite_limit(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("auto_notional_limit must be finite")
        return value

    @model_validator(mode="after")
    def conditional_requires_limit(self) -> "ApprovalPolicyConfig":
        if self.mode is ApprovalMode.CONDITIONAL and self.auto_notional_limit is None:
            raise ValueError("conditional approval requires auto_notional_limit")
        return self


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(frozen=True)
    approval_id: UUID
    status: ApprovalStatus
    reason: str
