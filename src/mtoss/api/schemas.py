from datetime import UTC, datetime
from decimal import Decimal, DecimalException
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from mtoss.application.intent_service import CreateIntentCommand, IntentCreationResult
from mtoss.domain.approvals import ApprovalMode, ApprovalPolicyConfig
from mtoss.domain.enums import OrderSide
from mtoss.domain.orders import validate_order_decimal_input
from mtoss.domain.risk import RiskRule


def _reject_inexact_or_non_finite(value: object, field_name: str) -> object:
    if isinstance(value, float):
        raise ValueError(f"{field_name} must not be a float")
    if isinstance(value, Decimal) and not value.is_finite():
        raise ValueError(f"{field_name} must be finite")
    if isinstance(value, str):
        try:
            parsed = Decimal(value)
        except DecimalException:
            return value
        if not parsed.is_finite():
            raise ValueError(f"{field_name} must be finite")
    return value


class CreateIntentRequest(BaseModel):
    account_id: UUID
    signal_id: UUID
    target_version: int = Field(ge=-2_147_483_648, le=2_147_483_647)
    market: str = Field(max_length=16)
    symbol: str = Field(max_length=32)
    side: OrderSide
    quantity: Decimal
    limit_price: Decimal | None
    currency: str = Field(max_length=8)
    expires_at: datetime
    account_capital: Decimal
    resulting_symbol_weight: Decimal
    daily_loss: Decimal
    drawdown: Decimal
    risk_rules: list[RiskRule]
    approval_mode: ApprovalMode
    auto_notional_limit: Decimal | None = None

    @field_validator(
        "quantity",
        "limit_price",
        "account_capital",
        "resulting_symbol_weight",
        "daily_loss",
        "drawdown",
        "auto_notional_limit",
        mode="before",
    )
    @classmethod
    def reject_inexact_or_non_finite_decimals(
        cls, value: object, info: object
    ) -> object:
        field_name = getattr(info, "field_name", "decimal")
        return _reject_inexact_or_non_finite(value, field_name)

    @field_validator("quantity", "limit_price")
    @classmethod
    def require_exact_order_database_decimal(
        cls, value: Decimal | None, info: object
    ) -> Decimal | None:
        if value is None:
            return value
        field_name = getattr(info, "field_name", "order decimal")
        validate_order_decimal_input(value, field_name)
        return value

    @field_validator("expires_at")
    @classmethod
    def normalize_expiration(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must be timezone-aware")
        return value.astimezone(UTC)


class CreateIntentResponse(BaseModel):
    intent_id: UUID
    state: str
    risk_decision_id: UUID
    approval_id: UUID

    @classmethod
    def from_result(cls, result: IntentCreationResult) -> "CreateIntentResponse":
        return cls(
            intent_id=result.intent_id,
            state=result.state.value,
            risk_decision_id=result.risk_decision_id,
            approval_id=result.approval_id,
        )


def to_command(payload: CreateIntentRequest) -> CreateIntentCommand:
    if payload.limit_price is None:
        raise ValueError("Phase 1 requires limit_price")
    return CreateIntentCommand(
        account_id=payload.account_id,
        signal_id=payload.signal_id,
        target_version=payload.target_version,
        market=payload.market,
        symbol=payload.symbol,
        side=payload.side,
        quantity=payload.quantity,
        limit_price=payload.limit_price,
        currency=payload.currency,
        expires_at=payload.expires_at,
        account_capital=payload.account_capital,
        resulting_symbol_weight=payload.resulting_symbol_weight,
        daily_loss=payload.daily_loss,
        drawdown=payload.drawdown,
        risk_rules=payload.risk_rules,
        approval_config=ApprovalPolicyConfig(
            mode=payload.approval_mode,
            auto_notional_limit=payload.auto_notional_limit,
        ),
    )
