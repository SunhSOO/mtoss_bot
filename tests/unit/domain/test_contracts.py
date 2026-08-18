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
