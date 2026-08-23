from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, DecimalException
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from mtoss.application.approval_policy import ApprovalPolicy
from mtoss.application.idempotency import build_intent_key
from mtoss.application.risk_engine import RiskEngine
from mtoss.domain.approvals import (
    ApprovalDecision,
    ApprovalPolicyConfig,
    ApprovalStatus,
)
from mtoss.domain.enums import OrderSide, OrderState, OrderType
from mtoss.domain.orders import ExecutionIntent
from mtoss.domain.risk import RiskContext, RiskDecision, RiskRule


class CreateIntentCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_id: UUID
    signal_id: UUID
    target_version: int
    market: str
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.LIMIT
    quantity: Decimal
    limit_price: Decimal | None = None
    reference_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    reduce_only: bool = False
    tranche_ref: str | None = None
    currency: str
    expires_at: datetime
    account_capital: Decimal
    resulting_symbol_weight: Decimal
    daily_loss: Decimal
    drawdown: Decimal
    risk_rules: list[RiskRule]
    approval_config: ApprovalPolicyConfig

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
        mode="before",
    )
    @classmethod
    def reject_float_or_non_finite_decimal(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("intent decimals must not be floats")
        candidate: Decimal | None = None
        if isinstance(value, Decimal):
            candidate = value
        elif isinstance(value, str):
            try:
                candidate = Decimal(value)
            except DecimalException:
                pass
        if candidate is not None and not candidate.is_finite():
            raise ValueError("intent decimals must be finite")
        return value

    @field_validator("expires_at")
    @classmethod
    def normalize_expiration(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_a_pricing_anchor(self) -> "CreateIntentCommand":
        if self.pricing_reference is None:
            raise ValueError("intent requires limit_price or reference_price")
        return self

    @property
    def pricing_reference(self) -> Decimal | None:
        """명목 산정 기준가. 지정가면 지정가, 시장가면 제출 시점 예상 체결가."""
        return self.limit_price if self.limit_price is not None else self.reference_price


class IntentCreationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    intent_id: UUID
    state: OrderState
    risk_decision_id: UUID
    approval_id: UUID


class RiskRejected(ValueError):
    def __init__(self, decision: RiskDecision) -> None:
        super().__init__("risk rejected")
        self.decision = decision


class IntentRepository(Protocol):
    async def record_risk_rejection(
        self,
        account_id: UUID,
        signal_id: UUID,
        decision: RiskDecision,
    ) -> None: ...

    async def create_with_outbox(
        self,
        intent: ExecutionIntent,
        state: OrderState,
        risk_decision_id: UUID,
        approval_id: UUID,
        risk_snapshot: dict[str, object],
        approval_snapshot: dict[str, object],
    ) -> UUID: ...


class RiskEvaluator(Protocol):
    def evaluate(self, context: RiskContext, rules: list[RiskRule]) -> RiskDecision: ...


class ApprovalDecider(Protocol):
    def decide(
        self,
        config: ApprovalPolicyConfig,
        order_notional: Decimal,
        now: datetime,
        expires_at: datetime,
    ) -> ApprovalDecision: ...


APPROVAL_STATES = {
    ApprovalStatus.APPROVED: OrderState.QUEUED,
    ApprovalStatus.PENDING: OrderState.PENDING_APPROVAL,
    ApprovalStatus.REJECTED: OrderState.REJECTED,
    ApprovalStatus.EXPIRED: OrderState.EXPIRED,
}


class IntentService:
    def __init__(
        self,
        repository: IntentRepository,
        *,
        risk_engine: RiskEvaluator | None = None,
        approval_policy: ApprovalDecider | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.risk_engine = risk_engine or RiskEngine()
        self.approval_policy = approval_policy or ApprovalPolicy()
        self.clock = clock or (lambda: datetime.now(UTC))

    async def create(self, command: CreateIntentCommand) -> IntentCreationResult:
        anchor = command.pricing_reference
        assert anchor is not None  # 모델 검증이 보장한다
        notional = command.quantity * anchor
        risk = self.risk_engine.evaluate(
            RiskContext(
                account_id=command.account_id,
                order_notional=notional,
                account_capital=command.account_capital,
                resulting_symbol_weight=command.resulting_symbol_weight,
                daily_loss=command.daily_loss,
                drawdown=command.drawdown,
            ),
            command.risk_rules,
        )
        if command.reduce_only and not risk.allowed:
            # 청산은 막지 않는다. 일일 손실 한도에 걸린 순간 손절도 못 내면 포지션에
            # 갇힌다. 위반 내역은 그대로 남겨 감사에서 보이게 한다.
            risk = risk.model_copy(update={"allowed": True})
        if not risk.allowed:
            await self.repository.record_risk_rejection(
                command.account_id,
                command.signal_id,
                risk,
            )
            raise RiskRejected(risk)

        approval = self.approval_policy.decide(
            command.approval_config,
            notional,
            self.clock(),
            command.expires_at,
        )
        state = APPROVAL_STATES[approval.status]
        intent_id = uuid4()
        intent = ExecutionIntent(
            intent_id=intent_id,
            account_id=command.account_id,
            signal_id=command.signal_id,
            target_version=command.target_version,
            market=command.market,
            symbol=command.symbol,
            side=command.side,
            order_type=command.order_type,
            quantity=command.quantity,
            limit_price=command.limit_price,
            reference_price=command.reference_price,
            stop_loss=command.stop_loss,
            take_profit=command.take_profit,
            reduce_only=command.reduce_only,
            tranche_ref=command.tranche_ref,
            currency=command.currency,
            expires_at=command.expires_at,
            idempotency_key=build_intent_key(
                command.account_id,
                command.signal_id,
                command.target_version,
                command.symbol,
                command.side,
            ),
        )
        await self.repository.create_with_outbox(
            intent,
            state,
            risk.decision_id,
            approval.approval_id,
            risk.model_dump(mode="json"),
            approval.model_dump(mode="json"),
        )
        return IntentCreationResult(
            intent_id=intent_id,
            state=state,
            risk_decision_id=risk.decision_id,
            approval_id=approval.approval_id,
        )
