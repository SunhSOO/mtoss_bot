# Execution Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a broker-independent, testable execution core that converts an approved normalized intent into one idempotent fake-broker order with durable state, risk evidence, approval evidence, audit events, and transactional outbox delivery.

**Architecture:** Use a modular Python monolith with pure domain contracts, application services, and infrastructure adapters. PostgreSQL is the source of truth; Redis Streams only transports outbox messages. A fake broker provides the first complete signal-to-order vertical slice without touching real accounts.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, PostgreSQL 16, Redis Streams, pytest, pytest-asyncio, Ruff, mypy, Docker Compose, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-08-18-system-trading-platform-design.md`

## Global Constraints

- Python runtime is exactly 3.12.x for the central server.
- PostgreSQL major version is 16; Redis Streams is the delivery transport.
- All money, price, quantity, weight, and limit values use `Decimal`, never binary float.
- Store timestamps as timezone-aware UTC values; reject naive datetimes at domain boundaries.
- PostgreSQL is the system of record. Redis data may be deleted without losing an accepted order intent.
- Delivery is at least once. Every consumer must be idempotent.
- Strategy and signal-source code cannot import or call broker adapters.
- No real broker credentials, MT5 terminal, or Toss API calls are introduced in this phase.
- `UNKNOWN` is a non-terminal state and must never trigger an automatic resubmission.
- Every task follows red → green → refactor and ends in one focused commit.

---

## Locked File Structure

```text
.
├─ pyproject.toml
├─ uv.lock
├─ compose.yaml
├─ .env.example
├─ alembic.ini
├─ alembic/
│  ├─ env.py
│  └─ versions/0001_execution_core.py
├─ src/mtoss/
│  ├─ __init__.py
│  ├─ config.py
│  ├─ domain/
│  │  ├─ enums.py
│  │  ├─ signals.py
│  │  ├─ orders.py
│  │  ├─ risk.py
│  │  └─ approvals.py
│  ├─ application/
│  │  ├─ idempotency.py
│  │  ├─ order_state_machine.py
│  │  ├─ risk_engine.py
│  │  ├─ approval_policy.py
│  │  ├─ intent_service.py
│  │  ├─ execution_service.py
│  │  └─ outbox_dispatcher.py
│  ├─ ports/
│  │  ├─ broker.py
│  │  └─ event_publisher.py
│  ├─ infrastructure/
│  │  ├─ db/base.py
│  │  ├─ db/session.py
│  │  ├─ db/models/order.py
│  │  ├─ db/models/outbox.py
│  │  ├─ db/models/audit.py
│  │  ├─ db/repositories/orders.py
│  │  ├─ db/repositories/outbox.py
│  │  ├─ queue/redis_streams.py
│  │  └─ broker/fake.py
│  └─ api/
│     ├─ app.py
│     ├─ dependencies.py
│     ├─ schemas.py
│     └─ routes/
│        ├─ health.py
│        └─ execution.py
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  │  └─ conftest.py
│  └─ api/
└─ .github/workflows/ci.yml
```

Domain files contain no SQLAlchemy, Redis, FastAPI, or broker imports. Application services depend on `ports` protocols. Infrastructure implements ports and persistence. API routes translate HTTP only.

---

### Task 1: Bootstrap the Python service and local infrastructure

**Files:**
- Create: `pyproject.toml`
- Create: `compose.yaml`
- Create: `.env.example`
- Create: `src/mtoss/__init__.py`
- Create: `src/mtoss/config.py`
- Create: `tests/unit/test_package.py`

**Interfaces:**
- Produces: importable `mtoss` package and `Settings` with `database_url`, `redis_url`, `internal_api_key`.
- Produces: PostgreSQL at `localhost:5432` and Redis at `localhost:6379` for later integration tasks.

- [ ] **Step 1: Write the failing package test**

```python
# tests/unit/test_package.py
from mtoss.config import Settings


def test_settings_accept_explicit_urls() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss",
        redis_url="redis://localhost:6379/0",
        internal_api_key="test-key",
    )
    assert settings.database_url.endswith("/mtoss")
    assert settings.redis_url.startswith("redis://")
```

- [ ] **Step 2: Run the test and verify the missing package failure**

Run: `python -m pytest tests/unit/test_package.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'mtoss'`.

- [ ] **Step 3: Create project metadata and settings**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mtoss-bot"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "alembic>=1.16",
  "asyncpg>=0.30",
  "fastapi>=0.116",
  "pydantic>=2.11",
  "pydantic-settings>=2.10",
  "redis>=6.0",
  "sqlalchemy[asyncio]>=2.0.43",
  "structlog>=25.0",
  "uvicorn[standard]>=0.35",
]

[dependency-groups]
dev = [
  "httpx>=0.28",
  "mypy>=1.17",
  "pytest>=8.4",
  "pytest-asyncio>=1.1",
  "ruff>=0.12",
]

[tool.hatch.build.targets.wheel]
packages = ["src/mtoss"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "ASYNC"]

[tool.mypy]
python_version = "3.12"
strict = true
packages = ["mtoss"]
```

```python
# src/mtoss/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    internal_api_key: str
```

Create an empty `src/mtoss/__init__.py`.

- [ ] **Step 4: Add local PostgreSQL and Redis**

```yaml
# compose.yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: mtoss
      POSTGRES_USER: mtoss
      POSTGRES_PASSWORD: mtoss
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mtoss -d mtoss"]
      interval: 2s
      timeout: 2s
      retries: 20
    volumes: ["postgres_data:/var/lib/postgresql/data"]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 2s
      timeout: 2s
      retries: 20

volumes:
  postgres_data:
```

```dotenv
# .env.example
DATABASE_URL=postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss
REDIS_URL=redis://localhost:6379/0
INTERNAL_API_KEY=replace-with-a-long-random-value
```

- [ ] **Step 5: Install, start services, and run the test**

Run:

```bash
uv sync --all-groups
docker compose up -d db redis
uv run pytest tests/unit/test_package.py -v
```

Expected: one passing test and healthy `db` and `redis` containers.

- [ ] **Step 6: Commit the bootstrap**

```bash
git add pyproject.toml uv.lock compose.yaml .env.example src/mtoss tests/unit/test_package.py
git commit -m "build: bootstrap execution core"
```

---

### Task 2: Define immutable domain contracts

**Files:**
- Create: `src/mtoss/domain/enums.py`
- Create: `src/mtoss/domain/signals.py`
- Create: `src/mtoss/domain/orders.py`
- Test: `tests/unit/domain/test_contracts.py`

**Interfaces:**
- Produces: `TradeSignal`, `ExecutionIntent`, `BrokerOrderResult` Pydantic models.
- Produces: `SourceType`, `SignalIntent`, `OrderSide`, `OrderState` string enums.
- Consumed later by: persistence, risk, approval, broker, API tasks.

- [ ] **Step 1: Write failing contract tests**

```python
# tests/unit/domain/test_contracts.py
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mtoss.domain.enums import OrderSide, SourceType
from mtoss.domain.orders import ExecutionIntent
from mtoss.domain.signals import TradeSignal


def test_trade_signal_rejects_naive_time() -> None:
    now = datetime.now()
    with pytest.raises(ValidationError):
        TradeSignal(
            signal_id=uuid4(),
            source_type=SourceType.STRATEGY,
            source_id="trend-v1",
            source_version="sha256:abc",
            generated_at=now,
            observed_at=now,
            expires_at=now + timedelta(seconds=90),
            market="MT5",
            symbol="USDJPY",
            currency="USD",
            target_weight=Decimal("0.10"),
            raw_payload_hash="a" * 64,
            trace_id=uuid4(),
        )


def test_execution_intent_preserves_decimal_quantity() -> None:
    intent = ExecutionIntent(
        intent_id=uuid4(), account_id=uuid4(), signal_id=uuid4(),
        target_version=1, market="KR", symbol="005930",
        side=OrderSide.BUY, quantity=Decimal("3"),
        limit_price=Decimal("72000"), currency="KRW",
        expires_at=datetime.now(UTC) + timedelta(seconds=90),
        idempotency_key="f" * 64,
    )
    assert intent.quantity == Decimal("3")


def test_execution_intent_rejects_non_positive_quantity() -> None:
    with pytest.raises(ValidationError):
        ExecutionIntent(
            intent_id=uuid4(), account_id=uuid4(), signal_id=uuid4(),
            target_version=1, market="US", symbol="AAPL",
            side=OrderSide.BUY, quantity=Decimal("0"),
            limit_price=Decimal("225"), currency="USD",
            expires_at=datetime.now(UTC) + timedelta(seconds=90),
            idempotency_key="f" * 64,
        )
```

- [ ] **Step 2: Run the tests and verify import failures**

Run: `uv run pytest tests/unit/domain/test_contracts.py -v`

Expected: FAIL because `mtoss.domain` modules do not exist.

- [ ] **Step 3: Implement enums and timezone validation**

```python
# src/mtoss/domain/enums.py
from enum import StrEnum


class SourceType(StrEnum):
    STRATEGY = "STRATEGY"
    LEADER = "LEADER"
    EXTERNAL = "EXTERNAL"
    FORM_13F = "FORM_13F"


class SignalIntent(StrEnum):
    TARGET_WEIGHT = "TARGET_WEIGHT"
    TARGET_QUANTITY = "TARGET_QUANTITY"
    CLOSE = "CLOSE"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderState(StrEnum):
    CREATED = "CREATED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    QUEUED = "QUEUED"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"
```

```python
# src/mtoss/domain/signals.py
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from mtoss.domain.enums import SourceType


class TradeSignal(BaseModel):
    model_config = ConfigDict(frozen=True)

    signal_id: UUID
    source_type: SourceType
    source_id: str
    source_version: str
    generated_at: datetime
    observed_at: datetime
    expires_at: datetime
    market: str
    symbol: str
    currency: str
    target_weight: Decimal
    raw_payload_hash: str
    trace_id: UUID

    @field_validator("generated_at", "observed_at", "expires_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_valid_window(self) -> "TradeSignal":
        if self.expires_at <= self.generated_at:
            raise ValueError("expires_at must be after generated_at")
        if not Decimal("-1") <= self.target_weight <= Decimal("1"):
            raise ValueError("target_weight must be between -1 and 1")
        return self
```

- [ ] **Step 4: Implement order contracts**

```python
# src/mtoss/domain/orders.py
from datetime import datetime
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
        return value

    @field_validator("quantity")
    @classmethod
    def require_positive_quantity(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("quantity must be positive")
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

    @field_validator("filled_quantity")
    @classmethod
    def require_non_negative_fill(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("filled_quantity cannot be negative")
        return value
```

- [ ] **Step 5: Run domain tests and static checks**

Run:

```bash
uv run pytest tests/unit/domain/test_contracts.py -v
uv run ruff check src/mtoss/domain tests/unit/domain
uv run mypy src/mtoss/domain
```

Expected: both tests pass; Ruff and mypy exit 0.

- [ ] **Step 6: Commit domain contracts**

```bash
git add src/mtoss/domain tests/unit/domain
git commit -m "feat: define execution domain contracts"
```

---

### Task 3: Add deterministic idempotency and order state transitions

**Files:**
- Create: `src/mtoss/application/idempotency.py`
- Create: `src/mtoss/application/order_state_machine.py`
- Test: `tests/unit/application/test_idempotency.py`
- Test: `tests/unit/application/test_order_state_machine.py`

**Interfaces:**
- Produces: `build_intent_key(account_id, signal_id, target_version, symbol, side) -> str`.
- Produces: `transition(current: OrderState, target: OrderState) -> OrderState`.
- Produces: `InvalidOrderTransition` exception.

- [ ] **Step 1: Write failing idempotency tests**

```python
# tests/unit/application/test_idempotency.py
from uuid import UUID

from mtoss.application.idempotency import build_intent_key
from mtoss.domain.enums import OrderSide


def test_intent_key_is_deterministic_and_side_sensitive() -> None:
    account = UUID("11111111-1111-1111-1111-111111111111")
    signal = UUID("22222222-2222-2222-2222-222222222222")
    buy_1 = build_intent_key(account, signal, 3, "AAPL", OrderSide.BUY)
    buy_2 = build_intent_key(account, signal, 3, "AAPL", OrderSide.BUY)
    sell = build_intent_key(account, signal, 3, "AAPL", OrderSide.SELL)
    assert buy_1 == buy_2
    assert buy_1 != sell
    assert len(buy_1) == 64
```

- [ ] **Step 2: Write failing state-machine tests**

```python
# tests/unit/application/test_order_state_machine.py
import pytest

from mtoss.application.order_state_machine import InvalidOrderTransition, transition
from mtoss.domain.enums import OrderState


def test_partial_fill_can_finish() -> None:
    assert transition(OrderState.PARTIALLY_FILLED, OrderState.FILLED) is OrderState.FILLED


def test_unknown_cannot_automatically_return_to_queued() -> None:
    with pytest.raises(InvalidOrderTransition):
        transition(OrderState.UNKNOWN, OrderState.QUEUED)


def test_filled_is_terminal() -> None:
    with pytest.raises(InvalidOrderTransition):
        transition(OrderState.FILLED, OrderState.CANCELED)
```

- [ ] **Step 3: Run tests and verify missing-module failures**

Run: `uv run pytest tests/unit/application/test_idempotency.py tests/unit/application/test_order_state_machine.py -v`

Expected: FAIL because application modules do not exist.

- [ ] **Step 4: Implement deterministic keys and explicit transitions**

```python
# src/mtoss/application/idempotency.py
import hashlib
from uuid import UUID

from mtoss.domain.enums import OrderSide


def build_intent_key(
    account_id: UUID,
    signal_id: UUID,
    target_version: int,
    symbol: str,
    side: OrderSide,
) -> str:
    canonical = "|".join(
        [str(account_id), str(signal_id), str(target_version), symbol.upper(), side.value]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

```python
# src/mtoss/application/order_state_machine.py
from mtoss.domain.enums import OrderState


class InvalidOrderTransition(ValueError):
    pass


ALLOWED: dict[OrderState, frozenset[OrderState]] = {
    OrderState.CREATED: frozenset({OrderState.PENDING_APPROVAL, OrderState.QUEUED, OrderState.REJECTED}),
    OrderState.PENDING_APPROVAL: frozenset({OrderState.QUEUED, OrderState.REJECTED, OrderState.EXPIRED}),
    OrderState.QUEUED: frozenset({OrderState.SUBMITTED, OrderState.REJECTED, OrderState.EXPIRED, OrderState.UNKNOWN}),
    OrderState.SUBMITTED: frozenset({OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCELED, OrderState.REJECTED, OrderState.UNKNOWN}),
    OrderState.PARTIALLY_FILLED: frozenset({OrderState.FILLED, OrderState.CANCELED, OrderState.UNKNOWN}),
    OrderState.UNKNOWN: frozenset({OrderState.SUBMITTED, OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCELED, OrderState.REJECTED}),
    OrderState.FILLED: frozenset(),
    OrderState.CANCELED: frozenset(),
    OrderState.REJECTED: frozenset(),
    OrderState.EXPIRED: frozenset(),
}


def transition(current: OrderState, target: OrderState) -> OrderState:
    if target not in ALLOWED[current]:
        raise InvalidOrderTransition(f"cannot transition {current.value} -> {target.value}")
    return target
```

- [ ] **Step 5: Run tests and checks**

Run:

```bash
uv run pytest tests/unit/application/test_idempotency.py tests/unit/application/test_order_state_machine.py -v
uv run ruff check src/mtoss/application tests/unit/application
uv run mypy src/mtoss/application
```

Expected: four tests pass; Ruff and mypy exit 0.

- [ ] **Step 6: Commit state safety**

```bash
git add src/mtoss/application tests/unit/application
git commit -m "feat: enforce idempotent order states"
```

---

### Task 4: Persist order intents, audit events, and transactional outbox

**Files:**
- Create: `src/mtoss/infrastructure/db/base.py`
- Create: `src/mtoss/infrastructure/db/session.py`
- Create: `src/mtoss/infrastructure/db/models/order.py`
- Create: `src/mtoss/infrastructure/db/models/outbox.py`
- Create: `src/mtoss/infrastructure/db/models/audit.py`
- Create: `src/mtoss/infrastructure/db/repositories/orders.py`
- Create: `src/mtoss/infrastructure/db/repositories/outbox.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/0001_execution_core.py`
- Test: `tests/integration/conftest.py`
- Test: `tests/integration/test_order_repository.py`

**Interfaces:**
- Produces: `OrderRepository.create_with_outbox(intent, state, risk_decision_id, approval_id, risk_snapshot, approval_snapshot) -> UUID`.
- Produces: `OrderRepository.get(order_id) -> OrderIntentRecord | None`.
- Produces: unique database constraint on `order_intents.idempotency_key`.
- Produces: `outbox_events` record in the same transaction as each accepted intent.

- [ ] **Step 1: Write the failing repository integration test**

```python
# tests/integration/test_order_repository.py
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from mtoss.domain.enums import OrderSide, OrderState
from mtoss.domain.orders import ExecutionIntent
from mtoss.infrastructure.db.repositories.orders import OrderRepository


@pytest.mark.asyncio
async def test_intent_and_outbox_are_atomic_and_idempotent(db_session) -> None:
    intent = ExecutionIntent(
        intent_id=uuid4(), account_id=uuid4(), signal_id=uuid4(), target_version=1,
        market="US", symbol="AAPL", side=OrderSide.BUY, quantity=Decimal("1"),
        limit_price=Decimal("225.10"), currency="USD",
        expires_at=datetime.now(UTC) + timedelta(seconds=90),
        idempotency_key="1" * 64,
    )
    repository = OrderRepository(db_session)
    await repository.create_with_outbox(
        intent, OrderState.QUEUED, uuid4(), uuid4(),
        {"allowed": True}, {"status": "APPROVED"},
    )
    await db_session.commit()
    assert await repository.count_orders() == 1
    assert await repository.count_unpublished_outbox() == 1
    assert await repository.count_audit_events() == 2

    with pytest.raises(IntegrityError):
        await repository.create_with_outbox(
            intent.model_copy(update={"intent_id": uuid4()}),
            OrderState.QUEUED,
            uuid4(),
            uuid4(),
            {"allowed": True},
            {"status": "APPROVED"},
        )
    await db_session.rollback()
```

- [ ] **Step 2: Start PostgreSQL and verify the test fails**

Run:

```bash
docker compose up -d db
uv run pytest tests/integration/test_order_repository.py -v
```

Expected: FAIL because DB models and fixtures do not exist.

- [ ] **Step 3: Implement the SQLAlchemy base, session, and records**

```python
# src/mtoss/infrastructure/db/base.py
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

```python
# src/mtoss/infrastructure/db/models/order.py
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, Enum, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from mtoss.domain.enums import OrderSide, OrderState
from mtoss.infrastructure.db.base import Base


class OrderIntentRecord(Base):
    __tablename__ = "order_intents"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_order_intent_idempotency"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    account_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    signal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    target_version: Mapped[int]
    market: Mapped[str] = mapped_column(String(16))
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[OrderSide] = mapped_column(Enum(OrderSide, native_enum=False))
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    currency: Mapped[str] = mapped_column(String(8))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(64))
    state: Mapped[OrderState] = mapped_column(Enum(OrderState, native_enum=False), index=True)
    broker_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(28, 10), default=Decimal("0"))
    average_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    broker_request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    risk_decision_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    approval_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
```

```python
# src/mtoss/infrastructure/db/models/outbox.py
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from mtoss.infrastructure.db.base import Base


class OutboxEventRecord(Base):
    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    topic: Mapped[str] = mapped_column(String(64), index=True)
    message_key: Mapped[str] = mapped_column(String(128), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

```python
# src/mtoss/infrastructure/db/models/audit.py
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from mtoss.infrastructure.db.base import Base


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    actor_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    trace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: Implement the transaction-scoped repository**

```python
# src/mtoss/infrastructure/db/repositories/orders.py
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mtoss.domain.enums import OrderState
from mtoss.domain.orders import ExecutionIntent
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
            id=intent.intent_id, account_id=intent.account_id, signal_id=intent.signal_id,
            target_version=intent.target_version, market=intent.market, symbol=intent.symbol,
            side=intent.side, quantity=intent.quantity, limit_price=intent.limit_price,
            currency=intent.currency, expires_at=intent.expires_at,
            idempotency_key=intent.idempotency_key, state=state,
            risk_decision_id=risk_decision_id, approval_id=approval_id,
        )
        self.session.add(record)
        self.session.add_all([
            AuditEventRecord(
                id=risk_decision_id, event_type="RISK_DECIDED",
                actor_id=None, trace_id=intent.signal_id, payload=risk_snapshot,
            ),
            AuditEventRecord(
                id=approval_id, event_type="APPROVAL_DECIDED",
                actor_id=None, trace_id=intent.signal_id, payload=approval_snapshot,
            ),
        ])
        if state is OrderState.QUEUED:
            self.session.add(OutboxEventRecord(
                id=uuid4(), topic="execution.intent.ready", message_key=intent.idempotency_key,
                payload={"intent_id": str(intent.intent_id), "account_id": str(intent.account_id)},
            ))
        await self.session.flush()
        return record.id

    async def count_orders(self) -> int:
        return int(await self.session.scalar(select(func.count()).select_from(OrderIntentRecord)) or 0)

    async def count_unpublished_outbox(self) -> int:
        statement = select(func.count()).select_from(OutboxEventRecord).where(
            OutboxEventRecord.published_at.is_(None)
        )
        return int(await self.session.scalar(statement) or 0)

    async def count_audit_events(self) -> int:
        return int(await self.session.scalar(select(func.count()).select_from(AuditEventRecord)) or 0)
```

- [ ] **Step 5: Add Alembic migration and integration fixture**

```ini
# alembic.ini
[alembic]
script_location = alembic
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic
[handlers]
keys = console
[formatters]
keys = generic
[logger_root]
level = WARN
handlers = console
qualname =
[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine
[logger_alembic]
level = INFO
handlers =
qualname = alembic
[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic
[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

```python
# alembic/env.py
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from mtoss.infrastructure.db.base import Base
from mtoss.infrastructure.db.models import audit, order, outbox  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
```

```python
# alembic/versions/0001_execution_core.py
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_execution_core"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "order_intents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_version", sa.Integer(), nullable=False),
        sa.Column("market", sa.String(16), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 10), nullable=False),
        sa.Column("limit_price", sa.Numeric(28, 10), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("broker_order_id", sa.String(128), nullable=True),
        sa.Column("filled_quantity", sa.Numeric(28, 10), nullable=False, server_default="0"),
        sa.Column("average_price", sa.Numeric(28, 10), nullable=True),
        sa.Column("broker_request_id", sa.String(128), nullable=True),
        sa.Column("error_code", sa.String(128), nullable=True),
        sa.Column("risk_decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_order_intent_idempotency"),
    )
    op.create_index("ix_order_intents_account_id", "order_intents", ["account_id"])
    op.create_index("ix_order_intents_signal_id", "order_intents", ["signal_id"])
    op.create_index("ix_order_intents_state", "order_intents", ["state"])
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("topic", sa.String(64), nullable=False),
        sa.Column("message_key", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_events_topic", "outbox_events", ["topic"])
    op.create_index("ix_outbox_events_message_key", "outbox_events", ["message_key"])
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_trace_id", "audit_events", ["trace_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("outbox_events")
    op.drop_table("order_intents")
```

```python
# src/mtoss/infrastructure/db/session.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def create_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)
```

```python
# tests/integration/conftest.py
import os

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss")
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()
```

Run migration before the test:

```bash
uv run alembic upgrade head
uv run pytest tests/integration/test_order_repository.py -v
```

Expected: repository test passes and the duplicate insert raises `IntegrityError` during flush.

- [ ] **Step 6: Run persistence checks and commit**

Run:

```bash
uv run ruff check src/mtoss/infrastructure tests/integration
uv run mypy src/mtoss/infrastructure
uv run pytest tests/integration/test_order_repository.py -v
```

Expected: all commands exit 0.

```bash
git add alembic.ini alembic src/mtoss/infrastructure tests/integration
git commit -m "feat: persist intents and outbox"
```

---

### Task 5: Dispatch outbox events through Redis Streams

**Files:**
- Create: `src/mtoss/ports/event_publisher.py`
- Create: `src/mtoss/infrastructure/queue/redis_streams.py`
- Create: `src/mtoss/infrastructure/db/repositories/outbox.py`
- Create: `src/mtoss/application/outbox_dispatcher.py`
- Test: `tests/unit/application/test_outbox_dispatcher.py`
- Test: `tests/integration/test_redis_publisher.py`

**Interfaces:**
- Produces: `EventPublisher.publish(topic: str, key: str, payload: dict[str, object]) -> str`.
- Produces: `OutboxDispatcher.dispatch_once(limit: int = 100) -> int`.
- Guarantees: failed publish leaves `published_at` null; successful publish marks it in PostgreSQL.

- [ ] **Step 1: Write the failing dispatcher test**

```python
# tests/unit/application/test_outbox_dispatcher.py
import pytest

from mtoss.application.outbox_dispatcher import OutboxDispatcher


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.events = [{"id": "1", "topic": "execution.intent.ready", "message_key": "k", "payload": {"intent_id": "i"}}]
        self.marked: list[str] = []

    async def claim(self, limit: int):
        return self.events[:limit]

    async def mark_published(self, event_id: str) -> None:
        self.marked.append(event_id)


class FakePublisher:
    async def publish(self, topic: str, key: str, payload: dict[str, object]) -> str:
        return "1-0"


@pytest.mark.asyncio
async def test_dispatch_marks_only_published_events() -> None:
    repository = FakeOutboxRepository()
    dispatched = await OutboxDispatcher(repository, FakePublisher()).dispatch_once()
    assert dispatched == 1
    assert repository.marked == ["1"]
```

- [ ] **Step 2: Run the test and verify missing-module failure**

Run: `uv run pytest tests/unit/application/test_outbox_dispatcher.py -v`

Expected: FAIL because dispatcher and publisher port do not exist.

- [ ] **Step 3: Implement the publisher port and dispatcher**

```python
# src/mtoss/ports/event_publisher.py
from typing import Protocol


class EventPublisher(Protocol):
    async def publish(self, topic: str, key: str, payload: dict[str, object]) -> str: ...
```

```python
# src/mtoss/application/outbox_dispatcher.py
from typing import Protocol

from mtoss.ports.event_publisher import EventPublisher


class OutboxRepositoryPort(Protocol):
    async def claim(self, limit: int) -> list[dict[str, object]]: ...
    async def mark_published(self, event_id: str) -> None: ...


class OutboxDispatcher:
    def __init__(self, repository: OutboxRepositoryPort, publisher: EventPublisher) -> None:
        self.repository = repository
        self.publisher = publisher

    async def dispatch_once(self, limit: int = 100) -> int:
        count = 0
        for event in await self.repository.claim(limit):
            await self.publisher.publish(
                str(event["topic"]), str(event["message_key"]), dict(event["payload"])
            )
            await self.repository.mark_published(str(event["id"]))
            count += 1
        return count
```

- [ ] **Step 4: Implement Redis Streams publishing**

```python
# src/mtoss/infrastructure/queue/redis_streams.py
import json

from redis.asyncio import Redis


class RedisStreamsPublisher:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def publish(self, topic: str, key: str, payload: dict[str, object]) -> str:
        message_id = await self.redis.xadd(
            topic,
            {"message_key": key, "payload": json.dumps(payload, separators=(",", ":"), sort_keys=True)},
        )
        return message_id.decode() if isinstance(message_id, bytes) else str(message_id)
```

```python
# src/mtoss/infrastructure/db/repositories/outbox.py
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mtoss.infrastructure.db.models.outbox import OutboxEventRecord


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim(self, limit: int) -> list[dict[str, object]]:
        statement = (
            select(OutboxEventRecord)
            .where(OutboxEventRecord.published_at.is_(None))
            .order_by(OutboxEventRecord.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        records = list((await self.session.scalars(statement)).all())
        return [
            {"id": str(record.id), "topic": record.topic,
             "message_key": record.message_key, "payload": record.payload}
            for record in records
        ]

    async def mark_published(self, event_id: str) -> None:
        record = await self.session.get(OutboxEventRecord, UUID(event_id))
        if record is None:
            raise LookupError(event_id)
        record.published_at = datetime.now(UTC)
        await self.session.commit()
```

```python
# tests/integration/test_redis_publisher.py
import json

import pytest
from redis.asyncio import Redis

from mtoss.infrastructure.queue.redis_streams import RedisStreamsPublisher


@pytest.mark.asyncio
async def test_redis_stream_contains_key_and_payload() -> None:
    redis = Redis.from_url("redis://localhost:6379/0")
    await redis.delete("test.execution")
    publisher = RedisStreamsPublisher(redis)
    await publisher.publish("test.execution", "k", {"intent_id": "i"})
    entries = await redis.xrange("test.execution")
    assert entries[0][1][b"message_key"] == b"k"
    assert json.loads(entries[0][1][b"payload"]) == {"intent_id": "i"}
    await redis.aclose()
```

- [ ] **Step 5: Verify Redis and failure behavior**

Run:

```bash
docker compose up -d redis
uv run pytest tests/unit/application/test_outbox_dispatcher.py tests/integration/test_redis_publisher.py -v
uv run ruff check src/mtoss/ports src/mtoss/application/outbox_dispatcher.py src/mtoss/infrastructure/queue
```

Add this second unit test to the dispatcher test file:

```python
class FailingPublisher:
    async def publish(self, topic: str, key: str, payload: dict[str, object]) -> str:
        raise ConnectionError("redis unavailable")


@pytest.mark.asyncio
async def test_failed_publish_is_not_marked() -> None:
    repository = FakeOutboxRepository()
    with pytest.raises(ConnectionError):
        await OutboxDispatcher(repository, FailingPublisher()).dispatch_once()
    assert repository.marked == []
```

Expected: unit and Redis integration tests pass; a failed publisher leaves the event unmarked.

- [ ] **Step 6: Commit outbox dispatch**

```bash
git add src/mtoss/ports src/mtoss/application/outbox_dispatcher.py src/mtoss/infrastructure/queue src/mtoss/infrastructure/db/repositories/outbox.py tests
git commit -m "feat: dispatch durable outbox events"
```

---

### Task 6: Implement fail-closed hierarchical risk evaluation

**Files:**
- Create: `src/mtoss/domain/risk.py`
- Create: `src/mtoss/application/risk_engine.py`
- Test: `tests/unit/application/test_risk_engine.py`

**Interfaces:**
- Produces: `RiskRule`, `RiskContext`, `RiskViolation`, `RiskDecision`.
- Produces: `RiskEngine.evaluate(context, rules) -> RiskDecision`.
- Required metrics: `ORDER_NOTIONAL`, `ACCOUNT_CAPITAL`, `SYMBOL_WEIGHT`, `DAILY_LOSS`, `MAX_DRAWDOWN`.

- [ ] **Step 1: Write failing strictest-limit and missing-rule tests**

```python
# tests/unit/application/test_risk_engine.py
from decimal import Decimal
from uuid import uuid4

from mtoss.application.risk_engine import RiskEngine
from mtoss.domain.risk import RiskContext, RiskMetric, RiskRule, RiskScope


def rules(order_limit: str) -> list[RiskRule]:
    return [
        RiskRule(rule_id=uuid4(), scope=RiskScope.SYSTEM, metric=RiskMetric.ORDER_NOTIONAL, limit=Decimal("1000000")),
        RiskRule(rule_id=uuid4(), scope=RiskScope.ACCOUNT, metric=RiskMetric.ORDER_NOTIONAL, limit=Decimal(order_limit)),
        RiskRule(rule_id=uuid4(), scope=RiskScope.ACCOUNT, metric=RiskMetric.ACCOUNT_CAPITAL, limit=Decimal("5000000")),
        RiskRule(rule_id=uuid4(), scope=RiskScope.ACCOUNT, metric=RiskMetric.SYMBOL_WEIGHT, limit=Decimal("0.20")),
        RiskRule(rule_id=uuid4(), scope=RiskScope.ACCOUNT, metric=RiskMetric.DAILY_LOSS, limit=Decimal("0.03")),
        RiskRule(rule_id=uuid4(), scope=RiskScope.ACCOUNT, metric=RiskMetric.MAX_DRAWDOWN, limit=Decimal("0.10")),
    ]


def test_more_restrictive_account_limit_wins() -> None:
    context = RiskContext(
        account_id=uuid4(), order_notional=Decimal("600000"), account_capital=Decimal("5000000"),
        resulting_symbol_weight=Decimal("0.12"), daily_loss=Decimal("0.01"), drawdown=Decimal("0.02"),
    )
    decision = RiskEngine().evaluate(context, rules("500000"))
    assert decision.allowed is False
    assert decision.violations[0].metric is RiskMetric.ORDER_NOTIONAL


def test_missing_required_metric_fails_closed() -> None:
    context = RiskContext(
        account_id=uuid4(), order_notional=Decimal("100"), account_capital=Decimal("1000"),
        resulting_symbol_weight=Decimal("0.10"), daily_loss=Decimal("0"), drawdown=Decimal("0"),
    )
    decision = RiskEngine().evaluate(context, rules("500")[0:1])
    assert decision.allowed is False
    assert {v.code for v in decision.violations} == {"MISSING_REQUIRED_LIMIT"}
```

- [ ] **Step 2: Run tests and verify missing types**

Run: `uv run pytest tests/unit/application/test_risk_engine.py -v`

Expected: FAIL because risk modules do not exist.

- [ ] **Step 3: Define risk models**

```python
# src/mtoss/domain/risk.py
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RiskScope(StrEnum):
    SYSTEM = "SYSTEM"
    USER = "USER"
    ACCOUNT = "ACCOUNT"
    SOURCE = "SOURCE"
    SYMBOL = "SYMBOL"


class RiskMetric(StrEnum):
    ORDER_NOTIONAL = "ORDER_NOTIONAL"
    ACCOUNT_CAPITAL = "ACCOUNT_CAPITAL"
    SYMBOL_WEIGHT = "SYMBOL_WEIGHT"
    DAILY_LOSS = "DAILY_LOSS"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"


class RiskRule(BaseModel):
    model_config = ConfigDict(frozen=True)
    rule_id: UUID
    scope: RiskScope
    metric: RiskMetric
    limit: Decimal


class RiskContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    account_id: UUID
    order_notional: Decimal
    account_capital: Decimal
    resulting_symbol_weight: Decimal
    daily_loss: Decimal
    drawdown: Decimal


class RiskViolation(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: str
    metric: RiskMetric | None
    actual: Decimal | None
    limit: Decimal | None


class RiskDecision(BaseModel):
    model_config = ConfigDict(frozen=True)
    decision_id: UUID
    allowed: bool
    violations: tuple[RiskViolation, ...]
```

- [ ] **Step 4: Implement strictest-limit evaluation**

```python
# src/mtoss/application/risk_engine.py
from decimal import Decimal
from uuid import uuid4

from mtoss.domain.risk import RiskContext, RiskDecision, RiskMetric, RiskRule, RiskViolation


REQUIRED = frozenset(RiskMetric)


class RiskEngine:
    def evaluate(self, context: RiskContext, rules: list[RiskRule]) -> RiskDecision:
        grouped: dict[RiskMetric, list[Decimal]] = {}
        for rule in rules:
            grouped.setdefault(rule.metric, []).append(rule.limit)
        missing = REQUIRED.difference(grouped)
        if missing:
            return RiskDecision(
                decision_id=uuid4(), allowed=False,
                violations=(RiskViolation(code="MISSING_REQUIRED_LIMIT", metric=None, actual=None, limit=None),),
            )
        actuals = {
            RiskMetric.ORDER_NOTIONAL: context.order_notional,
            RiskMetric.ACCOUNT_CAPITAL: context.account_capital,
            RiskMetric.SYMBOL_WEIGHT: context.resulting_symbol_weight,
            RiskMetric.DAILY_LOSS: context.daily_loss,
            RiskMetric.MAX_DRAWDOWN: context.drawdown,
        }
        violations = tuple(
            RiskViolation(code="LIMIT_EXCEEDED", metric=metric, actual=actuals[metric], limit=min(limits))
            for metric, limits in grouped.items()
            if actuals[metric] > min(limits)
        )
        return RiskDecision(decision_id=uuid4(), allowed=not violations, violations=violations)
```

- [ ] **Step 5: Run risk tests and checks**

Run:

```bash
uv run pytest tests/unit/application/test_risk_engine.py -v
uv run ruff check src/mtoss/domain/risk.py src/mtoss/application/risk_engine.py tests/unit/application/test_risk_engine.py
uv run mypy src/mtoss/domain/risk.py src/mtoss/application/risk_engine.py
```

Expected: both risk tests pass and static checks exit 0.

- [ ] **Step 6: Commit risk evaluation**

```bash
git add src/mtoss/domain/risk.py src/mtoss/application/risk_engine.py tests/unit/application/test_risk_engine.py
git commit -m "feat: add fail-closed risk engine"
```

---

### Task 7: Add source-specific approval policy and expiration

**Files:**
- Create: `src/mtoss/domain/approvals.py`
- Create: `src/mtoss/application/approval_policy.py`
- Test: `tests/unit/application/test_approval_policy.py`

**Interfaces:**
- Produces: `ApprovalMode`, `ApprovalPolicyConfig`, `ApprovalDecision`.
- Produces: `ApprovalPolicy.decide(config, order_notional, now, expires_at) -> ApprovalDecision`.
- States: `APPROVED`, `PENDING`, `REJECTED`, `EXPIRED`.

- [ ] **Step 1: Write failing policy tests**

```python
# tests/unit/application/test_approval_policy.py
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from mtoss.application.approval_policy import ApprovalPolicy
from mtoss.domain.approvals import ApprovalMode, ApprovalPolicyConfig, ApprovalStatus


def test_conditional_auto_requires_manual_above_threshold() -> None:
    config = ApprovalPolicyConfig(mode=ApprovalMode.CONDITIONAL, auto_notional_limit=Decimal("100000"))
    now = datetime.now(UTC)
    assert ApprovalPolicy().decide(config, Decimal("99999"), now, now + timedelta(seconds=90)).status is ApprovalStatus.APPROVED
    assert ApprovalPolicy().decide(config, Decimal("100001"), now, now + timedelta(seconds=90)).status is ApprovalStatus.PENDING


def test_expired_request_never_approves() -> None:
    now = datetime.now(UTC)
    config = ApprovalPolicyConfig(mode=ApprovalMode.AUTO, auto_notional_limit=None)
    decision = ApprovalPolicy().decide(config, Decimal("1"), now, now - timedelta(seconds=1))
    assert decision.status is ApprovalStatus.EXPIRED
```

- [ ] **Step 2: Run tests and verify missing-module failure**

Run: `uv run pytest tests/unit/application/test_approval_policy.py -v`

Expected: FAIL because approval modules do not exist.

- [ ] **Step 3: Implement approval models and decision rules**

```python
# src/mtoss/domain/approvals.py
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class ApprovalMode(StrEnum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    CONDITIONAL = "CONDITIONAL"


class ApprovalStatus(StrEnum):
    APPROVED = "APPROVED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ApprovalPolicyConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    mode: ApprovalMode
    auto_notional_limit: Decimal | None

    @model_validator(mode="after")
    def conditional_requires_limit(self) -> "ApprovalPolicyConfig":
        if self.mode is ApprovalMode.CONDITIONAL and self.auto_notional_limit is None:
            raise ValueError("conditional approval requires auto_notional_limit")
        return self


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(frozen=True)
    approval_id: UUID
    status: ApprovalStatus
    reason: str
```

```python
# src/mtoss/application/approval_policy.py
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from mtoss.domain.approvals import ApprovalDecision, ApprovalMode, ApprovalPolicyConfig, ApprovalStatus


class ApprovalPolicy:
    def decide(
        self,
        config: ApprovalPolicyConfig,
        order_notional: Decimal,
        now: datetime,
        expires_at: datetime,
    ) -> ApprovalDecision:
        if now >= expires_at:
            return ApprovalDecision(approval_id=uuid4(), status=ApprovalStatus.EXPIRED, reason="signal expired")
        if config.mode is ApprovalMode.AUTO:
            return ApprovalDecision(approval_id=uuid4(), status=ApprovalStatus.APPROVED, reason="auto policy")
        if config.mode is ApprovalMode.CONDITIONAL and order_notional <= config.auto_notional_limit:
            return ApprovalDecision(approval_id=uuid4(), status=ApprovalStatus.APPROVED, reason="within auto limit")
        return ApprovalDecision(approval_id=uuid4(), status=ApprovalStatus.PENDING, reason="manual approval required")
```

- [ ] **Step 4: Run approval tests and checks**

Run:

```bash
uv run pytest tests/unit/application/test_approval_policy.py -v
uv run ruff check src/mtoss/domain/approvals.py src/mtoss/application/approval_policy.py tests/unit/application/test_approval_policy.py
uv run mypy src/mtoss/domain/approvals.py src/mtoss/application/approval_policy.py
```

Expected: two tests pass and static checks exit 0.

- [ ] **Step 5: Add a regression test for missing conditional limit**

```python
import pytest
from pydantic import ValidationError


def test_conditional_mode_rejects_missing_threshold() -> None:
    with pytest.raises(ValidationError):
        ApprovalPolicyConfig(mode=ApprovalMode.CONDITIONAL, auto_notional_limit=None)
```

Run: `uv run pytest tests/unit/application/test_approval_policy.py -v`

Expected: three passing tests.

- [ ] **Step 6: Commit approval policy**

```bash
git add src/mtoss/domain/approvals.py src/mtoss/application/approval_policy.py tests/unit/application/test_approval_policy.py
git commit -m "feat: add approval policy"
```

---

### Task 8: Execute intents once through a fake broker

**Files:**
- Create: `src/mtoss/ports/broker.py`
- Create: `src/mtoss/infrastructure/broker/fake.py`
- Create: `src/mtoss/application/execution_service.py`
- Modify: `src/mtoss/infrastructure/db/repositories/orders.py`
- Test: `tests/unit/application/test_execution_service.py`
- Test: `tests/integration/test_execution_idempotency.py`

**Interfaces:**
- Produces: `BrokerAdapter.submit(intent) -> BrokerOrderResult`.
- Produces: `BrokerAdapter.lookup_by_client_order_id(account_id, client_order_id) -> BrokerOrderResult | None`.
- Produces: `ExecutionService.execute(intent_id: UUID) -> BrokerOrderResult`.
- Guarantees: only `QUEUED` orders with risk and approval evidence can submit; repeated execution does not call broker twice.

- [ ] **Step 1: Write the failing single-submit test**

```python
# tests/unit/application/test_execution_service.py
from decimal import Decimal
from uuid import uuid4

import pytest

from mtoss.application.execution_service import ExecutionService
from mtoss.domain.enums import OrderState
from mtoss.domain.orders import BrokerOrderResult, ExecutionIntent


class StubRecord:
    def __init__(self) -> None:
        from datetime import UTC, datetime, timedelta
        from mtoss.domain.enums import OrderSide

        self.intent = ExecutionIntent(
            intent_id=uuid4(), account_id=uuid4(), signal_id=uuid4(), target_version=1,
            market="US", symbol="AAPL", side=OrderSide.BUY, quantity=Decimal("1"),
            limit_price=Decimal("225"), currency="USD",
            expires_at=datetime.now(UTC) + timedelta(seconds=90), idempotency_key="a" * 64,
        )
        self.id = self.intent.intent_id
        self.state = OrderState.QUEUED
        self.risk_decision_id = uuid4()
        self.approval_id = uuid4()

    def as_domain(self) -> ExecutionIntent:
        return self.intent

    def as_broker_result(self) -> BrokerOrderResult:
        return BrokerOrderResult(
            client_order_id=self.intent.idempotency_key, broker_order_id="fake-1",
            state=self.state, filled_quantity=Decimal("0"), average_price=None,
            broker_request_id="req-1",
        )


@pytest.fixture
def queued_record() -> StubRecord:
    return StubRecord()


class FakeRepository:
    def __init__(self, record) -> None:
        self.record = record
        self.saved: list[BrokerOrderResult] = []

    async def lock_for_execution(self, intent_id):
        return self.record

    async def save_broker_result(self, intent_id, result):
        self.saved.append(result)
        self.record.state = result.state


class CountingBroker:
    def __init__(self) -> None:
        self.calls = 0

    async def submit(self, intent):
        self.calls += 1
        return BrokerOrderResult(
            client_order_id=intent.idempotency_key, broker_order_id="fake-1",
            state=OrderState.SUBMITTED, filled_quantity=Decimal("0"),
            average_price=None, broker_request_id="req-1",
        )

    async def lookup_by_client_order_id(self, account_id, client_order_id):
        return None


@pytest.mark.asyncio
async def test_execute_submits_queued_intent_once(queued_record) -> None:
    repository = FakeRepository(queued_record)
    broker = CountingBroker()
    service = ExecutionService(repository, broker)
    await service.execute(queued_record.id)
    await service.execute(queued_record.id)
    assert broker.calls == 1
```

- [ ] **Step 2: Write the ambiguous-timeout test**

```python
class TimeoutBroker(CountingBroker):
    async def submit(self, intent):
        self.calls += 1
        raise TimeoutError("response lost")


@pytest.mark.asyncio
async def test_timeout_becomes_unknown_without_second_submit(queued_record) -> None:
    repository = FakeRepository(queued_record)
    broker = TimeoutBroker()
    service = ExecutionService(repository, broker)
    result = await service.execute(queued_record.id)
    second = await service.execute(queued_record.id)
    assert result.state is OrderState.UNKNOWN
    assert second.state is OrderState.UNKNOWN
    assert broker.calls == 1
```

- [ ] **Step 3: Run tests and verify missing service failure**

Run: `uv run pytest tests/unit/application/test_execution_service.py -v`

Expected: FAIL because broker port and execution service do not exist.

- [ ] **Step 4: Implement broker port and execution behavior**

```python
# src/mtoss/ports/broker.py
from typing import Protocol
from uuid import UUID

from mtoss.domain.orders import BrokerOrderResult, ExecutionIntent


class BrokerAdapter(Protocol):
    async def submit(self, intent: ExecutionIntent) -> BrokerOrderResult: ...
    async def lookup_by_client_order_id(
        self, account_id: UUID, client_order_id: str
    ) -> BrokerOrderResult | None: ...
```

```python
# src/mtoss/application/execution_service.py
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from mtoss.domain.enums import OrderState
from mtoss.domain.orders import BrokerOrderResult, ExecutionIntent
from mtoss.ports.broker import BrokerAdapter


class ExecutionRecord(Protocol):
    id: UUID
    state: OrderState
    risk_decision_id: UUID | None
    approval_id: UUID | None

    def as_domain(self) -> ExecutionIntent: ...
    def as_broker_result(self) -> BrokerOrderResult: ...


class ExecutionRepository(Protocol):
    async def lock_for_execution(self, intent_id: UUID) -> ExecutionRecord: ...
    async def save_broker_result(self, intent_id: UUID, result: BrokerOrderResult) -> None: ...


class ExecutionService:
    def __init__(self, repository: ExecutionRepository, broker: BrokerAdapter) -> None:
        self.repository = repository
        self.broker = broker

    async def execute(self, intent_id: UUID) -> BrokerOrderResult:
        record = await self.repository.lock_for_execution(intent_id)
        if record.risk_decision_id is None or record.approval_id is None:
            raise PermissionError("risk and approval evidence are required")
        if record.state is not OrderState.QUEUED:
            return record.as_broker_result()
        intent = record.as_domain()
        try:
            result = await self.broker.submit(intent)
        except TimeoutError:
            known = await self.broker.lookup_by_client_order_id(
                intent.account_id, intent.idempotency_key
            )
            result = known or BrokerOrderResult(
                client_order_id=intent.idempotency_key, broker_order_id=None,
                state=OrderState.UNKNOWN, filled_quantity=Decimal("0"),
                average_price=None, broker_request_id=None, error_code="AMBIGUOUS_TIMEOUT",
            )
        await self.repository.save_broker_result(intent_id, result)
        return result
```

- [ ] **Step 5: Implement a deterministic fake broker and repository mapping**

`FakeBroker` stores results by `client_order_id`. A second `submit` for the same key returns the stored result without appending to `submitted_keys`.

```python
# src/mtoss/infrastructure/broker/fake.py
from decimal import Decimal
from uuid import UUID

from mtoss.domain.enums import OrderState
from mtoss.domain.orders import BrokerOrderResult, ExecutionIntent


class FakeBroker:
    def __init__(self) -> None:
        self.results: dict[str, BrokerOrderResult] = {}
        self.submitted_keys: list[str] = []

    async def submit(self, intent: ExecutionIntent) -> BrokerOrderResult:
        if intent.idempotency_key in self.results:
            return self.results[intent.idempotency_key]
        result = BrokerOrderResult(
            client_order_id=intent.idempotency_key,
            broker_order_id=f"fake-{len(self.results) + 1}",
            state=OrderState.SUBMITTED,
            filled_quantity=Decimal("0"), average_price=None,
            broker_request_id=f"fake-request-{len(self.results) + 1}",
        )
        self.results[intent.idempotency_key] = result
        self.submitted_keys.append(intent.idempotency_key)
        return result

    async def lookup_by_client_order_id(
        self, account_id: UUID, client_order_id: str
    ) -> BrokerOrderResult | None:
        return self.results.get(client_order_id)
```

Add these methods to the SQLAlchemy record and repository:

```python
# add to src/mtoss/infrastructure/db/models/order.py imports
from mtoss.domain.orders import BrokerOrderResult, ExecutionIntent

# add the following methods inside OrderIntentRecord
def as_domain(self) -> ExecutionIntent:
    return ExecutionIntent(
        intent_id=self.id, account_id=self.account_id, signal_id=self.signal_id,
        target_version=self.target_version, market=self.market, symbol=self.symbol,
        side=self.side, quantity=self.quantity, limit_price=self.limit_price,
        currency=self.currency, expires_at=self.expires_at,
        idempotency_key=self.idempotency_key,
    )

def as_broker_result(self) -> BrokerOrderResult:
    return BrokerOrderResult(
        client_order_id=self.idempotency_key, broker_order_id=self.broker_order_id,
        state=self.state, filled_quantity=self.filled_quantity,
        average_price=self.average_price, broker_request_id=self.broker_request_id,
        error_code=self.error_code,
    )
```

```python
# add to src/mtoss/infrastructure/db/repositories/orders.py imports
from mtoss.application.order_state_machine import transition
from mtoss.domain.orders import BrokerOrderResult

# add the following methods inside OrderRepository
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

async def save_broker_result(
    self, intent_id: UUID, result: BrokerOrderResult
) -> None:
    record = await self.lock_for_execution(intent_id)
    record.state = transition(record.state, result.state)
    record.broker_order_id = result.broker_order_id
    record.filled_quantity = result.filled_quantity
    record.average_price = result.average_price
    record.broker_request_id = result.broker_request_id
    record.error_code = result.error_code
    await self.session.flush()
```

- [ ] **Step 6: Prove database-level idempotency**

Create the integration test with one persisted queued intent, two execution calls, and one fake submission:

```python
# tests/integration/test_execution_idempotency.py
import pytest

from mtoss.application.execution_service import ExecutionService
from mtoss.domain.enums import OrderState
from mtoss.infrastructure.broker.fake import FakeBroker
from mtoss.infrastructure.db.repositories.orders import OrderRepository


@pytest.mark.asyncio
async def test_two_execution_attempts_submit_once(db_session, persisted_queued_intent) -> None:
    repository = OrderRepository(db_session)
    fake_broker = FakeBroker()
    service = ExecutionService(repository, fake_broker)
    await service.execute(persisted_queued_intent.intent_id)
    await db_session.commit()
    await service.execute(persisted_queued_intent.intent_id)
    await db_session.commit()
    persisted = await repository.get(persisted_queued_intent.intent_id)

    assert fake_broker.submitted_keys == [persisted_queued_intent.idempotency_key]
    assert persisted is not None
    assert persisted.state is OrderState.SUBMITTED
    assert await repository.count_orders() == 1
```

Add `OrderRepository.get` as:

```python
async def get(self, intent_id: UUID) -> OrderIntentRecord | None:
    return await self.session.get(OrderIntentRecord, intent_id)
```

Add this fixture to `tests/integration/conftest.py`:

```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from mtoss.domain.enums import OrderSide, OrderState
from mtoss.domain.orders import ExecutionIntent
from mtoss.infrastructure.db.repositories.orders import OrderRepository


@pytest_asyncio.fixture
async def persisted_queued_intent(db_session) -> ExecutionIntent:
    intent = ExecutionIntent(
        intent_id=uuid4(), account_id=uuid4(), signal_id=uuid4(), target_version=1,
        market="US", symbol="AAPL", side=OrderSide.BUY, quantity=Decimal("1"),
        limit_price=Decimal("225"), currency="USD",
        expires_at=datetime.now(UTC) + timedelta(seconds=90),
        idempotency_key="b" * 64,
    )
    await OrderRepository(db_session).create_with_outbox(
        intent, OrderState.QUEUED, uuid4(), uuid4(),
        {"allowed": True}, {"status": "APPROVED"},
    )
    await db_session.commit()
    return intent
```

Run:

```bash
uv run pytest tests/unit/application/test_execution_service.py tests/integration/test_execution_idempotency.py -v
uv run ruff check src/mtoss tests
uv run mypy src/mtoss
```

Expected: all tests pass and checks exit 0.

- [ ] **Step 7: Commit fake execution**

```bash
git add src/mtoss/ports/broker.py src/mtoss/infrastructure/broker src/mtoss/application/execution_service.py src/mtoss/infrastructure/db tests
git commit -m "feat: execute intents through fake broker"
```

---

### Task 9: Expose the vertical slice through an internal FastAPI endpoint

**Files:**
- Create: `src/mtoss/api/app.py`
- Create: `src/mtoss/api/dependencies.py`
- Create: `src/mtoss/api/schemas.py`
- Create: `src/mtoss/api/routes/health.py`
- Create: `src/mtoss/api/routes/execution.py`
- Create: `src/mtoss/application/intent_service.py`
- Test: `tests/api/test_health.py`
- Test: `tests/api/test_execution_flow.py`

**Interfaces:**
- Produces: `GET /health/live`, `GET /health/ready`.
- Produces: `POST /internal/v1/execution-intents` protected by `X-Internal-Key`.
- Produces: `GET /internal/v1/execution-intents/{intent_id}`.
- Consumes: `RiskEngine`, `ApprovalPolicy`, `OrderRepository`.

- [ ] **Step 1: Write failing health and authentication tests**

```python
# tests/api/test_health.py
from fastapi.testclient import TestClient

from mtoss.api.app import create_app
from mtoss.config import Settings


def test_liveness() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss",
        redis_url="redis://localhost:6379/0",
        internal_api_key="test-key",
    )
    response = TestClient(create_app(settings)).get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

```python
# tests/api/test_execution_flow.py
def test_internal_endpoint_requires_key(client) -> None:
    response = client.post("/internal/v1/execution-intents", json={})
    assert response.status_code == 401
```

- [ ] **Step 2: Run API tests and verify missing app failure**

Run: `uv run pytest tests/api -v`

Expected: FAIL because API modules do not exist.

- [ ] **Step 3: Implement app, health route, and internal-key dependency**

```python
# src/mtoss/api/app.py
from fastapi import FastAPI
from redis.asyncio import Redis

from mtoss.api.routes.execution import router as execution_router
from mtoss.api.routes.health import router as health_router
from mtoss.config import Settings
from mtoss.infrastructure.db.session import create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()
    app = FastAPI(title="mtoss execution core", version="0.1.0")
    app.state.settings = resolved
    app.state.session_factory = create_session_factory(resolved.database_url)
    app.state.redis = Redis.from_url(resolved.redis_url, decode_responses=True)
    app.include_router(health_router)
    app.include_router(execution_router)
    return app
```

```python
# src/mtoss/api/routes/health.py
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request) -> dict[str, str]:
    try:
        async with request.app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
        if not await request.app.state.redis.ping():
            raise RuntimeError("redis ping failed")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="dependencies unavailable") from exc
    return {"status": "ready"}
```

```python
# src/mtoss/api/dependencies.py
from fastapi import Header, HTTPException, Request, status


async def require_internal_key(
    request: Request,
    x_internal_key: str = Header(default=""),
) -> None:
    if x_internal_key != request.app.state.settings.internal_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid internal key")
```

- [ ] **Step 4: Define the request schema and intent orchestration**

```python
# src/mtoss/api/schemas.py
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from mtoss.domain.approvals import ApprovalMode
from mtoss.domain.enums import OrderSide
from mtoss.domain.risk import RiskRule


class CreateIntentRequest(BaseModel):
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
    account_capital: Decimal
    resulting_symbol_weight: Decimal
    daily_loss: Decimal
    drawdown: Decimal
    risk_rules: list[RiskRule]
    approval_mode: ApprovalMode
    auto_notional_limit: Decimal | None = None
```

```python
# src/mtoss/application/intent_service.py
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

from mtoss.application.approval_policy import ApprovalPolicy
from mtoss.application.idempotency import build_intent_key
from mtoss.application.risk_engine import RiskEngine
from mtoss.domain.approvals import ApprovalPolicyConfig, ApprovalStatus
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
        self, account_id: UUID, signal_id: UUID, decision: RiskDecision,
    ) -> None: ...

    async def create_with_outbox(
        self, intent: ExecutionIntent, state: OrderState,
        risk_decision_id: UUID, approval_id: UUID,
        risk_snapshot: dict[str, object], approval_snapshot: dict[str, object],
    ) -> UUID: ...


class IntentService:
    def __init__(self, repository: IntentRepository) -> None:
        self.repository = repository

    async def create(self, command: CreateIntentCommand) -> IntentCreationResult:
        notional = command.quantity * command.limit_price
        risk = RiskEngine().evaluate(
            RiskContext(
                account_id=command.account_id, order_notional=notional,
                account_capital=command.account_capital,
                resulting_symbol_weight=command.resulting_symbol_weight,
                daily_loss=command.daily_loss, drawdown=command.drawdown,
            ),
            command.risk_rules,
        )
        if not risk.allowed:
            await self.repository.record_risk_rejection(
                command.account_id, command.signal_id, risk,
            )
            raise RiskRejected(risk)
        approval = ApprovalPolicy().decide(
            command.approval_config, notional, datetime.now(command.expires_at.tzinfo),
            command.expires_at,
        )
        state = {
            ApprovalStatus.APPROVED: OrderState.QUEUED,
            ApprovalStatus.PENDING: OrderState.PENDING_APPROVAL,
            ApprovalStatus.REJECTED: OrderState.REJECTED,
            ApprovalStatus.EXPIRED: OrderState.EXPIRED,
        }[approval.status]
        intent_id = uuid4()
        intent = ExecutionIntent(
            intent_id=intent_id, account_id=command.account_id,
            signal_id=command.signal_id, target_version=command.target_version,
            market=command.market, symbol=command.symbol, side=command.side,
            quantity=command.quantity, limit_price=command.limit_price,
            currency=command.currency, expires_at=command.expires_at,
            idempotency_key=build_intent_key(
                command.account_id, command.signal_id, command.target_version,
                command.symbol, command.side,
            ),
        )
        await self.repository.create_with_outbox(
            intent, state, risk.decision_id, approval.approval_id,
            risk.model_dump(mode="json"), approval.model_dump(mode="json"),
        )
        return IntentCreationResult(
            intent_id=intent_id, state=state, risk_decision_id=risk.decision_id,
            approval_id=approval.approval_id,
        )
```

Add rejected-risk audit persistence to the SQLAlchemy repository:

```python
# add to src/mtoss/infrastructure/db/repositories/orders.py imports
from mtoss.domain.risk import RiskDecision

# add the following method inside OrderRepository
async def record_risk_rejection(
    self, account_id: UUID, signal_id: UUID, decision: RiskDecision,
) -> None:
    self.session.add(AuditEventRecord(
        id=decision.decision_id,
        event_type="RISK_REJECTED",
        actor_id=None,
        trace_id=signal_id,
        payload={
            "account_id": str(account_id),
            "decision": decision.model_dump(mode="json"),
        },
    ))
    await self.session.flush()
```

The Task 4 repository implementation already gates `OutboxEventRecord` creation on
`state is OrderState.QUEUED`; therefore manual, rejected, and expired intents remain
durable without becoming executable.

- [ ] **Step 5: Implement routes and the happy-path API test**

```python
# append to src/mtoss/api/schemas.py
from mtoss.application.intent_service import CreateIntentCommand, IntentCreationResult
from mtoss.domain.approvals import ApprovalPolicyConfig


class CreateIntentResponse(BaseModel):
    intent_id: UUID
    state: str
    risk_decision_id: UUID
    approval_id: UUID

    @classmethod
    def from_result(cls, result: IntentCreationResult) -> "CreateIntentResponse":
        return cls(
            intent_id=result.intent_id, state=result.state.value,
            risk_decision_id=result.risk_decision_id, approval_id=result.approval_id,
        )


def to_command(payload: CreateIntentRequest) -> CreateIntentCommand:
    if payload.limit_price is None:
        raise ValueError("Phase 1 requires limit_price")
    return CreateIntentCommand(
        account_id=payload.account_id, signal_id=payload.signal_id,
        target_version=payload.target_version, market=payload.market,
        symbol=payload.symbol, side=payload.side, quantity=payload.quantity,
        limit_price=payload.limit_price, currency=payload.currency,
        expires_at=payload.expires_at, account_capital=payload.account_capital,
        resulting_symbol_weight=payload.resulting_symbol_weight,
        daily_loss=payload.daily_loss, drawdown=payload.drawdown,
        risk_rules=payload.risk_rules,
        approval_config=ApprovalPolicyConfig(
            mode=payload.approval_mode,
            auto_notional_limit=payload.auto_notional_limit,
        ),
    )
```

```python
# src/mtoss/api/dependencies.py additions
from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from mtoss.application.intent_service import IntentService
from mtoss.infrastructure.db.repositories.orders import OrderRepository


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


async def get_intent_service(
    session: AsyncSession = Depends(get_session),
) -> IntentService:
    return IntentService(OrderRepository(session))
```

```python
# src/mtoss/api/routes/execution.py
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from mtoss.api.dependencies import get_intent_service, get_session, require_internal_key
from mtoss.api.schemas import CreateIntentRequest, CreateIntentResponse, to_command
from mtoss.application.intent_service import IntentService, RiskRejected
from mtoss.infrastructure.db.repositories.orders import OrderRepository

router = APIRouter(
    prefix="/internal/v1/execution-intents",
    tags=["execution"],
    dependencies=[Depends(require_internal_key)],
)


@router.post("", status_code=201, response_model=CreateIntentResponse)
async def create_intent(
    payload: CreateIntentRequest,
    service: IntentService = Depends(get_intent_service),
    session: AsyncSession = Depends(get_session),
) -> CreateIntentResponse:
    try:
        result = await service.create(to_command(payload))
    except RiskRejected as exc:
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "RISK_REJECTED", "decision_id": str(exc.decision.decision_id)},
        ) from exc
    await session.commit()
    return CreateIntentResponse.from_result(result)


@router.get("/{intent_id}")
async def get_intent(
    intent_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    record = await OrderRepository(session).get(intent_id)
    if record is None:
        raise HTTPException(status_code=404, detail="intent not found")
    return {"intent_id": str(record.id), "state": record.state.value}
```

Create explicit API fixtures so tests never depend on developer-machine secrets:

```python
# tests/api/conftest.py
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mtoss.api.app import create_app
from mtoss.config import Settings


@pytest.fixture
def client() -> TestClient:
    settings = Settings(
        database_url="postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss",
        redis_url="redis://localhost:6379/0",
        internal_api_key="test-key",
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def valid_payload() -> dict[str, object]:
    account_id = str(uuid4())
    return {
        "account_id": account_id,
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
            {"rule_id": str(uuid4()), "scope": "ACCOUNT", "metric": "ORDER_NOTIONAL", "limit": "10000"},
            {"rule_id": str(uuid4()), "scope": "ACCOUNT", "metric": "ACCOUNT_CAPITAL", "limit": "1000000"},
            {"rule_id": str(uuid4()), "scope": "ACCOUNT", "metric": "SYMBOL_WEIGHT", "limit": "0.20"},
            {"rule_id": str(uuid4()), "scope": "ACCOUNT", "metric": "DAILY_LOSS", "limit": "0.03"},
            {"rule_id": str(uuid4()), "scope": "ACCOUNT", "metric": "MAX_DRAWDOWN", "limit": "0.10"},
        ],
    }
```

Complete the happy-path test:

```python
# append to tests/api/test_execution_flow.py
def test_auto_approved_intent_is_queued(client, valid_payload) -> None:
    response = client.post(
        "/internal/v1/execution-intents",
        headers={"X-Internal-Key": "test-key"},
        json=valid_payload,
    )
    assert response.status_code == 201
    assert response.json()["state"] == "QUEUED"
```

Add this second test:

```python
def test_risk_rejection_returns_422(client, valid_payload) -> None:
    valid_payload["quantity"] = "1000000"
    response = client.post(
        "/internal/v1/execution-intents",
        headers={"X-Internal-Key": "test-key"},
        json=valid_payload,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "RISK_REJECTED"
```

- [ ] **Step 6: Run API and full tests**

Run:

```bash
uv run pytest tests/api -v
uv run pytest tests -v
uv run ruff check .
uv run mypy src/mtoss
```

Expected: all tests pass and static checks exit 0.

- [ ] **Step 7: Commit the API slice**

```bash
git add src/mtoss/api src/mtoss/application/intent_service.py tests/api
git commit -m "feat: expose execution intent API"
```

---

### Task 10: Add CI, migration verification, and operator documentation

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `README.md`
- Modify: `.gitignore`
- Test: full repository checks

**Interfaces:**
- Produces: reproducible CI on pull requests and pushes to `main`.
- Produces: exact local commands for boot, migration, test, and shutdown.

- [ ] **Step 1: Write the CI workflow**

```yaml
# .github/workflows/ci.yml
name: ci
on:
  pull_request:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: mtoss
          POSTGRES_USER: mtoss
          POSTGRES_PASSWORD: mtoss
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U mtoss -d mtoss"
          --health-interval 2s --health-timeout 2s --health-retries 20
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 2s --health-timeout 2s --health-retries 20
    env:
      DATABASE_URL: postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss
      TEST_DATABASE_URL: postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss
      REDIS_URL: redis://localhost:6379/0
      INTERNAL_API_KEY: ci-test-key
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.12"
          enable-cache: true
      - run: uv sync --all-groups --locked
      - run: uv run alembic upgrade head
      - run: uv run ruff check .
      - run: uv run mypy src/mtoss
      - run: uv run pytest tests -v
```

- [ ] **Step 2: Document exact operator commands**

Create `README.md` with these sections and commands:

```markdown
# mtoss_bot

Broker-independent execution core for the MT5 and Toss Securities trading platform.

## Local start

1. Copy `.env.example` to `.env` and replace `INTERNAL_API_KEY`.
2. Run `docker compose up -d db redis`.
3. Run `uv sync --all-groups --locked`.
4. Run `uv run alembic upgrade head`.
5. Run `uv run uvicorn mtoss.api.app:create_app --factory --reload`.

## Checks

- `uv run ruff check .`
- `uv run mypy src/mtoss`
- `uv run pytest tests -v`

## Stop

Run `docker compose down`. Add `-v` only when intentionally deleting local database data.

## Safety

This phase contains only `FakeBroker`; it cannot place real orders. Never commit `.env` or broker credentials.
```

- [ ] **Step 3: Extend secret and build exclusions**

Append these exact entries to `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
```

- [ ] **Step 4: Verify migration reproducibility on a fresh database**

Use an explicitly named disposable test database, not the development volume:

```bash
docker compose exec -T db dropdb -U mtoss --if-exists mtoss_ci_verify
docker compose exec -T db createdb -U mtoss mtoss_ci_verify
DATABASE_URL=postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify uv run alembic downgrade base
DATABASE_URL=postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify uv run alembic upgrade head
```

Expected: all migration commands exit 0. Drop only `mtoss_ci_verify` after verification.

- [ ] **Step 5: Run the complete Phase 1 verification**

Run:

```bash
uv sync --all-groups --locked
uv run ruff check .
uv run mypy src/mtoss
uv run pytest tests -v
git diff --check
```

Expected: all commands exit 0; pytest reports zero failures; `git diff --check` has no output.

- [ ] **Step 6: Commit CI and documentation**

```bash
git add .github/workflows/ci.yml README.md .gitignore
git commit -m "ci: verify execution core"
```

---

## Phase 1 Final Review Checklist

- [ ] `TradeSignal`, `ExecutionIntent`, and `BrokerOrderResult` reject invalid time or numeric inputs.
- [ ] Order state transitions match the approved design, including `UNKNOWN`.
- [ ] PostgreSQL has a unique idempotency constraint.
- [ ] Accepted intent and outbox event are committed in one transaction.
- [ ] Redis failure cannot erase the DB outbox event.
- [ ] Missing mandatory risk rules fail closed.
- [ ] Manual and conditional approval produce `PENDING_APPROVAL` correctly.
- [ ] Risk and approval evidence are required before broker submission.
- [ ] Repeated execution invokes `FakeBroker.submit` once per idempotency key.
- [ ] Timeout becomes `UNKNOWN` and does not resubmit.
- [ ] API tests cover unauthorized, queued, and risk-rejected requests.
- [ ] Fresh-database migration round-trip succeeds.
- [ ] Ruff, mypy, and the complete pytest suite pass in CI.
- [ ] No real broker package, credential, endpoint, or order call exists in Phase 1.
