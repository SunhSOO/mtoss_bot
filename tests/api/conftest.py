from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mtoss.api.app import create_app
from mtoss.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://mtoss:mtoss@127.0.0.1:1/mtoss",
        redis_url="redis://127.0.0.1:1/0",
        internal_api_key="test-key",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
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
