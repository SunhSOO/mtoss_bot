from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from mtoss.domain.enums import OrderSide, OrderState


class ExecutionIntent(BaseModel):
    model_config = ConfigDict(frozen=True)

    intent_id: UUID
    account_id: UUID
    signal_id: UUID
    target_version: int
    market: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    limit_price: Decimal | None
    currency: str
    expires_at: datetime
    idempotency_key: str

    @field_validator("expires_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("quantity", mode="before")
    @classmethod
    def reject_float_quantity(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("quantity must not be a float")
        return value

    @field_validator("quantity")
    @classmethod
    def require_positive_quantity(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("quantity must be positive")
        return value

    @field_validator("limit_price", mode="before")
    @classmethod
    def reject_float_limit_price(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("limit_price must not be a float")
        return value

    @field_validator("limit_price")
    @classmethod
    def require_positive_limit_price(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise ValueError("limit_price must be positive")
        return value

    @field_validator("idempotency_key")
    @classmethod
    def require_sha256_key(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("idempotency_key must be a lowercase SHA-256 hex digest")
        return value


class BrokerOrderResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_order_id: str
    broker_order_id: str | None
    state: OrderState
    filled_quantity: Decimal
    average_price: Decimal | None
    broker_request_id: str | None
    error_code: str | None = None

    @field_validator("filled_quantity", "average_price", mode="before")
    @classmethod
    def reject_float_money(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("money values must not be floats")
        return value

    @field_validator("filled_quantity")
    @classmethod
    def require_non_negative_fill(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("filled_quantity cannot be negative")
        return value
