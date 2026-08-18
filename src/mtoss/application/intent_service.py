from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, DecimalException
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, field_validator

from mtoss.application.approval_policy import ApprovalPolicy
from mtoss.application.idempotency import build_intent_key
from mtoss.application.risk_engine import RiskEngine
from mtoss.domain.approvals import (
    ApprovalDecision,
    ApprovalPolicyConfig,
    ApprovalStatus,
)
from mtoss.domain.enums import OrderSide, OrderState
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
    quantity: Decimal
    limit_price: Decimal
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
        notional = command.quantity * command.limit_price
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
            quantity=command.quantity,
            limit_price=command.limit_price,
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
