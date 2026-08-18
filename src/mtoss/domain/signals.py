from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from mtoss.domain.enums import SourceType


class TradeSignal(BaseModel):
    model_config = ConfigDict(frozen=True)

    signal_id: UUID
    source_type: SourceType
    source_id: str
    source_version: str
    generated_at: datetime
    observed_at: datetime
    expires_at: datetime
    market: str
    symbol: str
    currency: str
    target_weight: Decimal
    raw_payload_hash: str
    trace_id: UUID

    @field_validator("generated_at", "observed_at", "expires_at", mode="before")
    @classmethod
    def require_timezone(cls, value: object) -> object:
        if not isinstance(value, datetime):
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("target_weight", mode="before")
    @classmethod
    def reject_float_weight(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("target_weight must not be a float")
        return value

    @model_validator(mode="after")
    def require_valid_window(self) -> "TradeSignal":
        if self.expires_at <= self.generated_at:
            raise ValueError("expires_at must be after generated_at")
        if not Decimal("-1") <= self.target_weight <= Decimal("1"):
            raise ValueError("target_weight must be between -1 and 1")
        return self
