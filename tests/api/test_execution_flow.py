from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from mtoss.api.app import create_app
from mtoss.api.dependencies import get_intent_service, get_session
from mtoss.api.schemas import CreateIntentRequest, to_command
from mtoss.application.intent_service import CreateIntentCommand, IntentService
from mtoss.config import Settings
from mtoss.domain.approvals import ApprovalDecision, ApprovalStatus
from mtoss.domain.enums import OrderState
from mtoss.domain.orders import ExecutionIntent
from mtoss.domain.risk import RiskDecision
from mtoss.infrastructure.db.models.audit import AuditEventRecord
from mtoss.infrastructure.db.models.order import OrderIntentRecord
from mtoss.infrastructure.db.models.outbox import OutboxEventRecord
from mtoss.infrastructure.db.repositories.orders import OrderRepository


class FakeIntentRepository:
    def __init__(self) -> None:
        self.rejections: list[tuple[UUID, UUID, RiskDecision]] = []
        self.created: list[tuple[ExecutionIntent, OrderState]] = []

    async def record_risk_rejection(
        self, account_id: UUID, signal_id: UUID, decision: RiskDecision
    ) -> None:
        self.rejections.append((account_id, signal_id, decision))

    async def create_with_outbox(
        self,
        intent: ExecutionIntent,
        state: OrderState,
        risk_decision_id: UUID,
        approval_id: UUID,
        risk_snapshot: dict[str, object],
        approval_snapshot: dict[str, object],
    ) -> UUID:
        self.created.append((intent, state))
        return intent.intent_id


class FakeSession:
    def __init__(self, *, fail_commit: bool = False, record: object | None = None) -> None:
        self.fail_commit = fail_commit
        self.record = record
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("commit failed")

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def get(self, _model: object, _identifier: UUID) -> object | None:
        return self.record


def make_client(
    settings: Settings,
    service: object,
    session: FakeSession,
) -> TestClient:
    app = create_app(settings)

    async def override_session() -> AsyncIterator[FakeSession]:
        yield session

    app.dependency_overrides[get_intent_service] = lambda: service
    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def test_internal_endpoint_requires_key(client: TestClient) -> None:
    response = client.post("/internal/v1/execution-intents", json={})
    assert response.status_code == 401


def test_settings_reject_blank_internal_key(settings: Settings) -> None:
    with pytest.raises(ValidationError, match="internal_api_key must not be blank"):
        Settings(
            database_url=settings.database_url,
            redis_url=settings.redis_url,
            internal_api_key=" \t ",
        )


def test_app_rechecks_internal_key_after_unvalidated_settings_copy(settings: Settings) -> None:
    bypassed = settings.model_copy(update={"internal_api_key": "  "})
    with pytest.raises(ValueError, match="internal_api_key must not be blank"):
        create_app(bypassed)


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-Internal-Key": "   "},
        {"X-Internal-Key": "wrong-key"},
        [(b"x-internal-key", "잘못된키".encode())],
    ],
    ids=["missing", "blank", "wrong", "non-ascii"],
)
def test_internal_endpoint_rejects_invalid_key_without_server_error(
    settings: Settings,
    valid_payload: dict[str, object],
    headers: object,
) -> None:
    with make_client(settings, IntentService(FakeIntentRepository()), FakeSession()) as client:
        response = client.post(
            "/internal/v1/execution-intents",
            headers=headers,  # type: ignore[arg-type]
            json=valid_payload,
        )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid internal key"}


def test_internal_key_comes_from_injected_app_settings(
    settings: Settings, valid_payload: dict[str, object]
) -> None:
    repository = FakeIntentRepository()
    session = FakeSession()
    settings = settings.model_copy(update={"internal_api_key": "injected-secret"})
    with make_client(settings, IntentService(repository), session) as client:
        wrong = client.post(
            "/internal/v1/execution-intents",
            headers={"X-Internal-Key": "test-key"},
            json=valid_payload,
        )
        right = client.post(
            "/internal/v1/execution-intents",
            headers={"X-Internal-Key": "injected-secret"},
            json=valid_payload,
        )
    assert wrong.status_code == 401
    assert right.status_code == 201


def test_auto_approved_intent_is_queued_and_committed(
    settings: Settings, valid_payload: dict[str, object]
) -> None:
    repository = FakeIntentRepository()
    session = FakeSession()
    with make_client(settings, IntentService(repository), session) as client:
        response = client.post(
            "/internal/v1/execution-intents",
            headers={"X-Internal-Key": "test-key"},
            json=valid_payload,
        )
    assert response.status_code == 201
    assert response.json()["state"] == "QUEUED"
    assert repository.created[0][1] is OrderState.QUEUED
    assert session.commits == 1
    assert session.rollbacks == 0


def test_exact_decimal_strings_and_offset_timestamp_reach_the_domain_exactly(
    settings: Settings, valid_payload: dict[str, object]
) -> None:
    repository = FakeIntentRepository()
    session = FakeSession()
    valid_payload["quantity"] = "0.1"
    valid_payload["limit_price"] = "225.10"
    expiry = datetime.now(timezone(timedelta(hours=9))) + timedelta(seconds=90)
    valid_payload["expires_at"] = expiry.isoformat()
    with make_client(settings, IntentService(repository), session) as client:
        response = client.post(
            "/internal/v1/execution-intents",
            headers={"X-Internal-Key": "test-key"},
            json=valid_payload,
        )
    intent = repository.created[0][0]
    assert response.status_code == 201
    assert intent.quantity == Decimal("0.1")
    assert intent.limit_price == Decimal("225.10")
    assert intent.expires_at.tzinfo is UTC
    assert intent.expires_at == expiry.astimezone(UTC)


@pytest.mark.parametrize("invalid_value", [0.1, "NaN", "Infinity", "-Infinity", "not-a-number"])
def test_request_rejects_binary_float_and_non_finite_decimal(
    settings: Settings, valid_payload: dict[str, object], invalid_value: object
) -> None:
    repository = FakeIntentRepository()
    session = FakeSession()
    valid_payload["quantity"] = invalid_value
    with make_client(settings, IntentService(repository), session) as client:
        response = client.post(
            "/internal/v1/execution-intents",
            headers={"X-Internal-Key": "test-key"},
            json=valid_payload,
        )
    assert response.status_code == 422
    assert repository.created == []


def test_request_requires_an_aware_expiration_timestamp(
    settings: Settings, valid_payload: dict[str, object]
) -> None:
    repository = FakeIntentRepository()
    session = FakeSession()
    valid_payload["expires_at"] = "2026-08-18T12:00:00"
    with make_client(settings, IntentService(repository), session) as client:
        response = client.post(
            "/internal/v1/execution-intents",
            headers={"X-Internal-Key": "test-key"},
            json=valid_payload,
        )
    assert response.status_code == 422
    assert repository.created == []


def test_risk_rejection_is_audited_then_committed(
    settings: Settings, valid_payload: dict[str, object]
) -> None:
    repository = FakeIntentRepository()
    session = FakeSession()
    valid_payload["quantity"] = "1000000"
    with make_client(settings, IntentService(repository), session) as client:
        response = client.post(
            "/internal/v1/execution-intents",
            headers={"X-Internal-Key": "test-key"},
            json=valid_payload,
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "RISK_REJECTED"
    assert len(repository.rejections) == 1
    assert repository.created == []
    assert session.commits == 1
    assert session.rollbacks == 0


class FixedApprovalPolicy:
    def __init__(self, status: ApprovalStatus) -> None:
        self.status = status

    def decide(self, *_args: object) -> ApprovalDecision:
        return ApprovalDecision(approval_id=uuid4(), status=self.status, reason="test policy")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("approval_status", "expected_state"),
    [
        (ApprovalStatus.APPROVED, OrderState.QUEUED),
        (ApprovalStatus.PENDING, OrderState.PENDING_APPROVAL),
        (ApprovalStatus.REJECTED, OrderState.REJECTED),
        (ApprovalStatus.EXPIRED, OrderState.EXPIRED),
    ],
)
async def test_intent_service_maps_every_approval_status_explicitly(
    valid_payload: dict[str, object],
    approval_status: ApprovalStatus,
    expected_state: OrderState,
) -> None:
    repository = FakeIntentRepository()
    command = to_command(CreateIntentRequest.model_validate(valid_payload))
    service = IntentService(repository, approval_policy=FixedApprovalPolicy(approval_status))
    result = await service.create(command)
    assert result.state is expected_state
    assert repository.created[0][1] is expected_state


class CaptureSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flushed = False

    def add(self, record: object) -> None:
        self.added.append(record)

    def add_all(self, records: list[object]) -> None:
        self.added.extend(records)

    async def flush(self) -> None:
        self.flushed = True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state", [OrderState.PENDING_APPROVAL, OrderState.REJECTED, OrderState.EXPIRED]
)
async def test_non_queued_intents_persist_without_an_execution_event(
    valid_payload: dict[str, object], state: OrderState
) -> None:
    command = to_command(CreateIntentRequest.model_validate(valid_payload))
    intent = ExecutionIntent(
        intent_id=uuid4(),
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
        idempotency_key="a" * 64,
    )
    session = CaptureSession()
    await OrderRepository(session).create_with_outbox(  # type: ignore[arg-type]
        intent, state, uuid4(), uuid4(), {"allowed": True}, {"status": state.value}
    )
    assert sum(isinstance(record, OrderIntentRecord) for record in session.added) == 1
    assert not any(isinstance(record, OutboxEventRecord) for record in session.added)
    assert session.flushed


@pytest.mark.asyncio
async def test_sql_repository_records_rejected_risk_audit() -> None:
    session = CaptureSession()
    decision = RiskDecision(decision_id=uuid4(), allowed=False, violations=())
    account_id = uuid4()
    signal_id = uuid4()
    await OrderRepository(session).record_risk_rejection(  # type: ignore[arg-type]
        account_id, signal_id, decision
    )
    audit = session.added[0]
    assert isinstance(audit, AuditEventRecord)
    assert audit.event_type == "RISK_REJECTED"
    assert audit.trace_id == signal_id
    assert audit.payload["account_id"] == str(account_id)
    assert session.flushed


class ExplodingService:
    async def create(self, _command: CreateIntentCommand) -> Any:
        raise RuntimeError("service failed")


class DuplicateService:
    async def create(self, _command: CreateIntentCommand) -> Any:
        raise IntegrityError("INSERT INTO order_intents", {}, Exception("unique violation"))


def test_duplicate_intent_rolls_back_and_returns_conflict(
    settings: Settings, valid_payload: dict[str, object]
) -> None:
    session = FakeSession()
    with make_client(settings, DuplicateService(), session) as client:
        response = client.post(
            "/internal/v1/execution-intents",
            headers={"X-Internal-Key": "test-key"},
            json=valid_payload,
        )
    assert response.status_code == 409
    assert response.json() == {"detail": {"code": "DUPLICATE_INTENT"}}
    assert session.commits == 0
    assert session.rollbacks == 1


def test_unexpected_creation_failure_rolls_back(
    settings: Settings, valid_payload: dict[str, object]
) -> None:
    session = FakeSession()
    with make_client(settings, ExplodingService(), session) as client:
        with pytest.raises(RuntimeError, match="service failed"):
            client.post(
                "/internal/v1/execution-intents",
                headers={"X-Internal-Key": "test-key"},
                json=valid_payload,
            )
    assert session.commits == 0
    assert session.rollbacks == 1


def test_failed_commit_is_rolled_back(
    settings: Settings, valid_payload: dict[str, object]
) -> None:
    session = FakeSession(fail_commit=True)
    with make_client(settings, IntentService(FakeIntentRepository()), session) as client:
        with pytest.raises(RuntimeError, match="commit failed"):
            client.post(
                "/internal/v1/execution-intents",
                headers={"X-Internal-Key": "test-key"},
                json=valid_payload,
            )
    assert session.commits == 1
    assert session.rollbacks == 1


def test_get_intent_is_authenticated_and_returns_persisted_state(settings: Settings) -> None:
    intent_id = uuid4()
    record = SimpleNamespace(id=intent_id, state=OrderState.PENDING_APPROVAL)
    session = FakeSession(record=record)
    with make_client(settings, IntentService(FakeIntentRepository()), session) as client:
        unauthorized = client.get(f"/internal/v1/execution-intents/{intent_id}")
        response = client.get(
            f"/internal/v1/execution-intents/{intent_id}",
            headers={"X-Internal-Key": "test-key"},
        )
    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json() == {"intent_id": str(intent_id), "state": "PENDING_APPROVAL"}
