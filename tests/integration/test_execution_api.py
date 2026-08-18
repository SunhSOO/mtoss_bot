import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from mtoss.api.app import create_app
from mtoss.config import Settings
from mtoss.infrastructure.db.models.audit import AuditEventRecord
from mtoss.infrastructure.db.models.order import OrderIntentRecord
from mtoss.infrastructure.db.models.outbox import OutboxEventRecord

DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss"
)
INTERNAL_KEY = "integration-key"


def valid_payload() -> dict[str, object]:
    return {
        "account_id": str(uuid4()),
        "signal_id": str(uuid4()),
        "target_version": 1,
        "market": "US",
        "symbol": "AAPL",
        "side": "BUY",
        "quantity": "1",
        "limit_price": "225.10",
        "currency": "USD",
        "expires_at": (datetime.now(UTC) + timedelta(seconds=90)).isoformat(),
        "account_capital": "500000",
        "resulting_symbol_weight": "0.05",
        "daily_loss": "0",
        "drawdown": "0",
        "approval_mode": "AUTO",
        "risk_rules": [
            {
                "rule_id": str(uuid4()),
                "scope": "ACCOUNT",
                "metric": "ORDER_NOTIONAL",
                "limit": "10000",
            },
            {
                "rule_id": str(uuid4()),
                "scope": "ACCOUNT",
                "metric": "ACCOUNT_CAPITAL",
                "limit": "1000000",
            },
            {
                "rule_id": str(uuid4()),
                "scope": "ACCOUNT",
                "metric": "SYMBOL_WEIGHT",
                "limit": "0.20",
            },
            {
                "rule_id": str(uuid4()),
                "scope": "ACCOUNT",
                "metric": "DAILY_LOSS",
                "limit": "0.03",
            },
            {
                "rule_id": str(uuid4()),
                "scope": "ACCOUNT",
                "metric": "MAX_DRAWDOWN",
                "limit": "0.10",
            },
        ],
    }


def production_client() -> TestClient:
    settings = Settings(
        database_url=DATABASE_URL,
        redis_url="redis://localhost:6379/0",
        internal_api_key=INTERNAL_KEY,
    )
    return TestClient(create_app(settings))


async def cleanup_trace(session: AsyncSession, signal_id: UUID, account_id: UUID) -> None:
    await session.execute(delete(AuditEventRecord).where(AuditEventRecord.trace_id == signal_id))
    await session.execute(
        delete(OutboxEventRecord).where(
            OutboxEventRecord.payload["account_id"].astext == str(account_id)
        )
    )
    await session.execute(delete(OrderIntentRecord).where(OrderIntentRecord.signal_id == signal_id))
    await session.commit()


@pytest.mark.asyncio
async def test_repeated_post_persists_one_correlated_queued_slice_and_returns_409() -> None:
    payload = valid_payload()
    signal_id = UUID(str(payload["signal_id"]))
    account_id = UUID(str(payload["account_id"]))

    with production_client() as client:
        first = client.post(
            "/internal/v1/execution-intents",
            headers={"X-Internal-Key": INTERNAL_KEY},
            json=payload,
        )
        duplicate = client.post(
            "/internal/v1/execution-intents",
            headers={"X-Internal-Key": INTERNAL_KEY},
            json=payload,
        )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": {"code": "DUPLICATE_INTENT"}}

    engine = create_async_engine(DATABASE_URL)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            record = await session.scalar(
                select(OrderIntentRecord).where(OrderIntentRecord.signal_id == signal_id)
            )
            assert record is not None
            message_key = record.idempotency_key
            try:
                orders = await session.scalar(
                    select(func.count())
                    .select_from(OrderIntentRecord)
                    .where(OrderIntentRecord.signal_id == signal_id)
                )
                audits = list(
                    await session.scalars(
                        select(AuditEventRecord).where(AuditEventRecord.trace_id == signal_id)
                    )
                )
                outbox = list(
                    await session.scalars(
                        select(OutboxEventRecord).where(
                            OutboxEventRecord.message_key == message_key
                        )
                    )
                )

                assert orders == 1
                assert record.state.value == "QUEUED"
                audit_by_type = {event.event_type: event for event in audits}
                assert set(audit_by_type) == {"RISK_DECIDED", "APPROVAL_DECIDED"}
                assert audit_by_type["RISK_DECIDED"].payload["allowed"] is True
                assert audit_by_type["APPROVAL_DECIDED"].payload["status"] == "APPROVED"
                assert len(outbox) == 1
                assert outbox[0].topic == "execution.intent.ready"
                assert outbox[0].payload == {
                    "intent_id": str(record.id),
                    "account_id": str(account_id),
                }
            finally:
                await cleanup_trace(session, signal_id, account_id)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_rejected_risk_post_commits_audit_without_order_or_outbox() -> None:
    payload = valid_payload()
    payload["quantity"] = "1000000"
    signal_id = UUID(str(payload["signal_id"]))
    account_id = UUID(str(payload["account_id"]))

    with production_client() as client:
        response = client.post(
            "/internal/v1/execution-intents",
            headers={"X-Internal-Key": INTERNAL_KEY},
            json=payload,
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "RISK_REJECTED"
    decision_id = UUID(response.json()["detail"]["decision_id"])

    engine = create_async_engine(DATABASE_URL)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                audit = await session.scalar(
                    select(AuditEventRecord).where(AuditEventRecord.trace_id == signal_id)
                )
                order_count = await session.scalar(
                    select(func.count())
                    .select_from(OrderIntentRecord)
                    .where(OrderIntentRecord.signal_id == signal_id)
                )
                outbox_count = await session.scalar(
                    select(func.count()).select_from(OutboxEventRecord).where(
                        OutboxEventRecord.payload["account_id"].astext == str(account_id)
                    )
                )

                assert audit is not None
                assert audit.id == decision_id
                assert audit.event_type == "RISK_REJECTED"
                assert audit.payload["account_id"] == str(account_id)
                decision = audit.payload["decision"]
                assert isinstance(decision, dict)
                assert decision["allowed"] is False
                assert decision["violations"]
                assert order_count == 0
                assert outbox_count == 0
            finally:
                await cleanup_trace(session, signal_id, account_id)
    finally:
        await engine.dispose()
