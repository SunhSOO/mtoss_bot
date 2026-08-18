from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from mtoss.domain.enums import OrderSide, OrderState
from mtoss.domain.orders import BrokerOrderResult, ExecutionIntent
from mtoss.infrastructure.db.base import Base


class OrderIntentRecord(Base):
    __tablename__ = "order_intents"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_order_intent_idempotency"),
        CheckConstraint("quantity > 0", name="ck_order_intents_quantity_positive"),
        CheckConstraint(
            "limit_price IS NULL OR limit_price > 0",
            name="ck_order_intents_limit_price_positive",
        ),
        CheckConstraint(
            "filled_quantity >= 0",
            name="ck_order_intents_filled_quantity_non_negative",
        ),
        CheckConstraint(
            "average_price IS NULL OR average_price > 0",
            name="ck_order_intents_average_price_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    account_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    signal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    target_version: Mapped[int]
    market: Mapped[str] = mapped_column(String(16))
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[OrderSide] = mapped_column(Enum(OrderSide, native_enum=False, length=16))
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    currency: Mapped[str] = mapped_column(String(8))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(64))
    state: Mapped[OrderState] = mapped_column(
        Enum(OrderState, native_enum=False, length=32), index=True
    )
    broker_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    filled_quantity: Mapped[Decimal] = mapped_column(
        Numeric(28, 10), default=Decimal("0"), server_default="0"
    )
    average_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    broker_request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    risk_decision_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    approval_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))

    def as_domain(self) -> ExecutionIntent:
        return ExecutionIntent(
            intent_id=self.id,
            account_id=self.account_id,
            signal_id=self.signal_id,
            target_version=self.target_version,
            market=self.market,
            symbol=self.symbol,
            side=self.side,
            quantity=self.quantity,
            limit_price=self.limit_price,
            currency=self.currency,
            expires_at=self.expires_at,
            idempotency_key=self.idempotency_key,
        )

    def as_broker_result(self) -> BrokerOrderResult:
        return BrokerOrderResult(
            client_order_id=self.idempotency_key,
            broker_order_id=self.broker_order_id,
            state=self.state,
            filled_quantity=self.filled_quantity,
            average_price=self.average_price,
            broker_request_id=self.broker_request_id,
            error_code=self.error_code,
        )
