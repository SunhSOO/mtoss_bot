from datetime import UTC, datetime
from decimal import Decimal, DecimalException
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from mtoss.domain.enums import OrderSide, OrderState, OrderType

ORDER_NUMERIC_PRECISION = 28
ORDER_NUMERIC_SCALE = 10
ORDER_NUMERIC_INTEGER_DIGITS = ORDER_NUMERIC_PRECISION - ORDER_NUMERIC_SCALE


def validate_order_decimal_input(value: object, field_name: str) -> object:
    if isinstance(value, float):
        raise ValueError(f"{field_name} must not be a float")

    candidate: Decimal | None = None
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, (int, str)):
        try:
            candidate = Decimal(value)
        except DecimalException:
            pass
    if candidate is None:
        return value
    if not candidate.is_finite():
        raise ValueError(f"{field_name} must be finite")

    exponent = int(candidate.as_tuple().exponent)
    scale = max(-exponent, 0)
    integer_digits = 0 if candidate == 0 else max(candidate.adjusted() + 1, 0)
    if (
        scale > ORDER_NUMERIC_SCALE
        or integer_digits > ORDER_NUMERIC_INTEGER_DIGITS
        or integer_digits + scale > ORDER_NUMERIC_PRECISION
    ):
        raise ValueError(f"{field_name} must fit PostgreSQL NUMERIC(28,10) exactly")
    return value


class ExecutionIntent(BaseModel):
    model_config = ConfigDict(frozen=True)

    intent_id: UUID
    account_id: UUID
    signal_id: UUID
    target_version: int
    market: str
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.LIMIT
    quantity: Decimal
    limit_price: Decimal | None
    reference_price: Decimal | None = None
    """시장가 주문에서 명목·리스크 산정에 쓸 예상 체결가. 지정가면 `limit_price`가 대신한다."""

    stop_loss: Decimal | None = None
    """브로커 서버에 심는 손절가. 헤징 계좌라 포지션마다 따로 걸린다 — 이 서버가
    꺼져 있어도 손절이 작동하게 만드는 값이다."""

    take_profit: Decimal | None = None
    reduce_only: bool = False
    """청산 전용 주문. 진입 차단 리스크 룰을 우회한다 — 손절이 막히면 포지션에 갇힌다."""

    tranche_ref: str | None = None
    """이 주문이 속한 트랜치(T1/T2). 브래킷 수정·부분 청산에서 대상을 특정한다."""

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
        return validate_order_decimal_input(value, "quantity")

    @field_validator("quantity")
    @classmethod
    def require_positive_quantity(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("quantity must be positive")
        return value

    @field_validator("limit_price", mode="before")
    @classmethod
    def reject_float_limit_price(cls, value: object) -> object:
        if value is None:
            return value
        return validate_order_decimal_input(value, "limit_price")

    @field_validator("limit_price")
    @classmethod
    def require_positive_limit_price(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise ValueError("limit_price must be positive")
        return value

    @field_validator("reference_price", "stop_loss", "take_profit", mode="before")
    @classmethod
    def reject_float_bracket(cls, value: object) -> object:
        if value is None:
            return value
        return validate_order_decimal_input(value, "bracket price")

    @field_validator("reference_price", "stop_loss", "take_profit")
    @classmethod
    def require_positive_bracket(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise ValueError("bracket prices must be positive")
        return value

    @field_validator("tranche_ref")
    @classmethod
    def require_short_tranche_ref(cls, value: str | None) -> str | None:
        if value is not None and (not value or len(value) > 16):
            raise ValueError("tranche_ref must be 1-16 characters")
        return value

    @field_validator("idempotency_key")
    @classmethod
    def require_sha256_key(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("idempotency_key must be a lowercase SHA-256 hex digest")
        return value

    @model_validator(mode="after")
    def require_consistent_pricing(self) -> "ExecutionIntent":
        if self.order_type is OrderType.LIMIT:
            if self.limit_price is None:
                raise ValueError("limit orders require limit_price")
        elif self.limit_price is not None:
            raise ValueError("market orders must not carry a limit_price")
        elif self.reference_price is None:
            raise ValueError("market orders require reference_price for risk sizing")
        return self

    @model_validator(mode="after")
    def require_brackets_on_the_correct_side(self) -> "ExecutionIntent":
        """손절이 진입가의 반대편에 있으면 즉시 체결되거나 브로커가 거부한다.

        조용히 통과시키면 실계좌에서만 드러나므로 여기서 막는다.
        """
        anchor = self.pricing_reference
        if anchor is None:
            return self
        if self.side is OrderSide.BUY:
            if self.stop_loss is not None and self.stop_loss >= anchor:
                raise ValueError("buy stop_loss must sit below the entry price")
            if self.take_profit is not None and self.take_profit <= anchor:
                raise ValueError("buy take_profit must sit above the entry price")
        else:
            if self.stop_loss is not None and self.stop_loss <= anchor:
                raise ValueError("sell stop_loss must sit above the entry price")
            if self.take_profit is not None and self.take_profit >= anchor:
                raise ValueError("sell take_profit must sit below the entry price")
        return self

    @property
    def pricing_reference(self) -> Decimal | None:
        """명목·리스크 산정과 브래킷 방향 검사의 기준가."""
        return self.limit_price if self.limit_price is not None else self.reference_price


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
        if value is None:
            return value
        return validate_order_decimal_input(value, "order result decimal")

    @field_validator("filled_quantity")
    @classmethod
    def require_non_negative_fill(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("filled_quantity cannot be negative")
        return value

    @field_validator("average_price")
    @classmethod
    def require_positive_average_price(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise ValueError("average_price must be positive")
        return value


class BrokerPosition(BaseModel):
    """브로커가 실제로 들고 있는 포지션 하나.

    헤징 계좌라 주문 하나가 포지션 하나가 되고, 각자 티켓과 각자 SL/TP를 갖는다.
    정합성 조정기가 "우리 장부"와 이걸 대조한다 — 어긋나면 브로커 쪽이 진실이다.
    """

    model_config = ConfigDict(frozen=True)

    position_ref: str
    """브로커 측 식별자. MT5에서는 포지션 티켓."""

    account_id: UUID
    symbol: str
    side: OrderSide
    quantity: Decimal
    entry_price: Decimal
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    tranche_ref: str | None = None
    opened_at: datetime | None = None

    @field_validator("quantity", "entry_price", "stop_loss", "take_profit", mode="before")
    @classmethod
    def reject_float_position_value(cls, value: object) -> object:
        if value is None:
            return value
        return validate_order_decimal_input(value, "position decimal")

    @field_validator("quantity", "entry_price")
    @classmethod
    def require_positive_position_value(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("position quantity and entry price must be positive")
        return value

    @field_validator("opened_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("opened_at must be timezone-aware")
        return value.astimezone(UTC)
