from datetime import UTC, datetime
from decimal import Decimal, DecimalException
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from mtoss.application.intent_service import CreateIntentCommand, IntentCreationResult
from mtoss.domain.approvals import ApprovalMode, ApprovalPolicyConfig
from mtoss.domain.enums import OrderSide, OrderType
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
    order_type: OrderType = OrderType.LIMIT
    quantity: Decimal
    limit_price: Decimal | None
    reference_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    reduce_only: bool = False
    tranche_ref: str | None = Field(default=None, max_length=16)
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
        "reference_price",
        "stop_loss",
        "take_profit",
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

    @field_validator("quantity", "limit_price", "reference_price", "stop_loss", "take_profit")
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
    if payload.order_type is OrderType.LIMIT and payload.limit_price is None:
        raise ValueError("limit orders require limit_price")
    if payload.order_type is OrderType.MARKET:
        if payload.limit_price is not None:
            raise ValueError("market orders must not carry a limit_price")
        if payload.reference_price is None:
            raise ValueError("market orders require reference_price for risk sizing")
    return CreateIntentCommand(
        account_id=payload.account_id,
        signal_id=payload.signal_id,
        target_version=payload.target_version,
        market=payload.market,
        symbol=payload.symbol,
        side=payload.side,
        order_type=payload.order_type,
        quantity=payload.quantity,
        limit_price=payload.limit_price,
        reference_price=payload.reference_price,
        stop_loss=payload.stop_loss,
        take_profit=payload.take_profit,
        reduce_only=payload.reduce_only,
        tranche_ref=payload.tranche_ref,
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
