from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mtoss.application.order_state_machine import transition
from mtoss.domain.enums import OrderState
from mtoss.domain.orders import BrokerOrderResult, ExecutionIntent
from mtoss.domain.risk import RiskDecision
from mtoss.infrastructure.db.models.audit import AuditEventRecord
from mtoss.infrastructure.db.models.order import OrderIntentRecord
from mtoss.infrastructure.db.models.outbox import OutboxEventRecord


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_with_outbox(
        self,
        intent: ExecutionIntent,
        state: OrderState,
        risk_decision_id: UUID,
        approval_id: UUID,
        risk_snapshot: dict[str, object],
        approval_snapshot: dict[str, object],
    ) -> UUID:
        record = OrderIntentRecord(
            id=intent.intent_id,
            account_id=intent.account_id,
            signal_id=intent.signal_id,
            target_version=intent.target_version,
            market=intent.market,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            limit_price=intent.limit_price,
            currency=intent.currency,
            expires_at=intent.expires_at,
            idempotency_key=intent.idempotency_key,
            state=state,
            risk_decision_id=risk_decision_id,
            approval_id=approval_id,
        )
        self.session.add(record)
        self.session.add_all(
            [
                AuditEventRecord(
                    id=risk_decision_id,
                    event_type="RISK_DECIDED",
                    actor_id=None,
                    trace_id=intent.signal_id,
                    payload=risk_snapshot,
                ),
                AuditEventRecord(
                    id=approval_id,
                    event_type="APPROVAL_DECIDED",
                    actor_id=None,
                    trace_id=intent.signal_id,
                    payload=approval_snapshot,
                ),
            ]
        )
        if state is OrderState.QUEUED:
            self.session.add(
                OutboxEventRecord(
                    id=uuid4(),
                    topic="execution.intent.ready",
                    message_key=intent.idempotency_key,
                    payload={
                        "intent_id": str(intent.intent_id),
                        "account_id": str(intent.account_id),
                    },
                )
            )
        await self.session.flush()
        return record.id

    async def record_risk_rejection(
        self,
        account_id: UUID,
        signal_id: UUID,
        decision: RiskDecision,
    ) -> None:
        self.session.add(
            AuditEventRecord(
                id=decision.decision_id,
                event_type="RISK_REJECTED",
                actor_id=None,
                trace_id=signal_id,
                payload={
                    "account_id": str(account_id),
                    "decision": decision.model_dump(mode="json"),
                },
            )
        )
        await self.session.flush()

    async def get(self, order_id: UUID) -> OrderIntentRecord | None:
        return await self.session.get(OrderIntentRecord, order_id)

    async def lock_for_execution(self, intent_id: UUID) -> OrderIntentRecord:
        statement = (
            select(OrderIntentRecord)
            .where(OrderIntentRecord.id == intent_id)
            .with_for_update()
        )
        record = await self.session.scalar(statement)
        if record is None:
            raise LookupError(str(intent_id))
        return record

    async def save_broker_result(self, intent_id: UUID, result: BrokerOrderResult) -> None:
        try:
            record = await self.lock_for_execution(intent_id)
            if result.client_order_id != record.idempotency_key:
                raise ValueError(
                    "broker result client order ID does not match stored idempotency key"
                )
            if record.state is OrderState.QUEUED and result.state in {
                OrderState.PARTIALLY_FILLED,
                OrderState.FILLED,
                OrderState.CANCELED,
            }:
                record.state = transition(record.state, OrderState.SUBMITTED)
            record.state = transition(record.state, result.state)
            record.broker_order_id = result.broker_order_id
            record.filled_quantity = result.filled_quantity
            record.average_price = result.average_price
            record.broker_request_id = result.broker_request_id
            record.error_code = result.error_code
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def release_execution_lock(self) -> None:
        await self.session.rollback()

    async def count_orders(self) -> int:
        statement = select(func.count()).select_from(OrderIntentRecord)
        return int(await self.session.scalar(statement) or 0)

    async def count_unpublished_outbox(self) -> int:
        statement = select(func.count()).select_from(OutboxEventRecord).where(
            OutboxEventRecord.published_at.is_(None)
        )
        return int(await self.session.scalar(statement) or 0)

    async def count_audit_events(self) -> int:
        statement = select(func.count()).select_from(AuditEventRecord)
        return int(await self.session.scalar(statement) or 0)
