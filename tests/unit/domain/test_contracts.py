from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mtoss.domain.enums import OrderSide, OrderState, SourceType
from mtoss.domain.orders import BrokerOrderResult, ExecutionIntent
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


def test_trade_signal_normalizes_aware_times_to_utc() -> None:
    local_time = datetime(2026, 1, 1, 9, 0, tzinfo=timezone(timedelta(hours=9)))
    signal = TradeSignal(
        signal_id=uuid4(), source_type=SourceType.STRATEGY,
        source_id="trend-v1", source_version="sha256:abc",
        generated_at=local_time, observed_at=local_time,
        expires_at=local_time + timedelta(seconds=90), market="MT5",
        symbol="USDJPY", currency="USD", target_weight=Decimal("0.10"),
        raw_payload_hash="a" * 64, trace_id=uuid4(),
    )
    assert signal.generated_at == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert signal.generated_at.tzinfo is UTC


def test_execution_intent_normalizes_aware_expiry_to_utc() -> None:
    local_time = datetime(2026, 1, 1, 9, 0, tzinfo=timezone(timedelta(hours=9)))
    intent = ExecutionIntent(
        intent_id=uuid4(), account_id=uuid4(), signal_id=uuid4(),
        target_version=1, market="KR", symbol="005930", side=OrderSide.BUY,
        quantity=Decimal("3"), limit_price=Decimal("72000"), currency="KRW",
        expires_at=local_time, idempotency_key="f" * 64,
    )
    assert intent.expires_at == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert intent.expires_at.tzinfo is UTC


def test_trade_signal_parses_and_normalizes_timestamp_strings() -> None:
    signal = TradeSignal(
        signal_id=uuid4(), source_type=SourceType.STRATEGY,
        source_id="trend-v1", source_version="sha256:abc",
        generated_at="2026-01-01T09:00:00+09:00",
        observed_at="2026-01-01T09:00:00+09:00",
        expires_at="2026-01-01T09:01:30+09:00", market="MT5",
        symbol="USDJPY", currency="USD", target_weight=Decimal("0.10"),
        raw_payload_hash="a" * 64, trace_id=uuid4(),
    )
    assert signal.generated_at == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert signal.expires_at.tzinfo is UTC


def test_trade_signal_rejects_naive_timestamp_string() -> None:
    with pytest.raises(ValidationError):
        TradeSignal(
            signal_id=uuid4(), source_type=SourceType.STRATEGY,
            source_id="trend-v1", source_version="sha256:abc",
            generated_at="2026-01-01T09:00:00",
            observed_at="2026-01-01T09:00:00Z",
            expires_at="2026-01-01T09:01:30Z", market="MT5",
            symbol="USDJPY", currency="USD", target_weight=Decimal("0.10"),
            raw_payload_hash="a" * 64, trace_id=uuid4(),
        )


def test_execution_intent_parses_and_normalizes_timestamp_string() -> None:
    intent = ExecutionIntent(
        intent_id=uuid4(), account_id=uuid4(), signal_id=uuid4(),
        target_version=1, market="KR", symbol="005930", side=OrderSide.BUY,
        quantity=Decimal("3"), limit_price=Decimal("72000"), currency="KRW",
        expires_at="2026-01-01T09:00:00+09:00", idempotency_key="f" * 64,
    )
    assert intent.expires_at == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert intent.expires_at.tzinfo is UTC


@pytest.mark.parametrize("field, value", [
    ("quantity", "0"), ("quantity", -1),
    ("limit_price", "0"), ("limit_price", -1),
])
def test_execution_intent_rejects_non_positive_numeric_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        ExecutionIntent(
            intent_id=uuid4(), account_id=uuid4(), signal_id=uuid4(),
            target_version=1, market="KR", symbol="005930", side=OrderSide.BUY,
            quantity=value if field == "quantity" else Decimal("3"),
            limit_price=value if field == "limit_price" else Decimal("72000"),
            currency="KRW", expires_at=datetime.now(UTC), idempotency_key="f" * 64,
        )


@pytest.mark.parametrize("value", ["-1", -1])
def test_broker_order_result_rejects_negative_filled_quantity(value: object) -> None:
    with pytest.raises(ValidationError):
        BrokerOrderResult(
            client_order_id="client-1", broker_order_id="broker-1",
            state=OrderState.FILLED, filled_quantity=value,
            average_price=Decimal("72000"), broker_request_id="request-1",
        )


@pytest.mark.parametrize("field", ["target_weight"])
def test_trade_signal_rejects_float_decimal_fields(field: str) -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        TradeSignal(
            signal_id=uuid4(), source_type=SourceType.STRATEGY,
            source_id="trend-v1", source_version="sha256:abc",
            generated_at=now, observed_at=now,
            expires_at=now + timedelta(seconds=90), market="MT5",
            symbol="USDJPY", currency="USD", **{field: 0.1},
            raw_payload_hash="a" * 64, trace_id=uuid4(),
        )


@pytest.mark.parametrize("field", ["quantity", "limit_price"])
def test_execution_intent_rejects_float_decimal_fields(field: str) -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        ExecutionIntent(
            intent_id=uuid4(), account_id=uuid4(), signal_id=uuid4(),
            target_version=1, market="KR", symbol="005930", side=OrderSide.BUY,
            quantity=0.1 if field == "quantity" else Decimal("3"),
            limit_price=0.1 if field == "limit_price" else Decimal("72000"),
            currency="KRW", expires_at=now, idempotency_key="f" * 64,
        )


@pytest.mark.parametrize("field", ["filled_quantity", "average_price"])
def test_broker_order_result_rejects_float_decimal_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        BrokerOrderResult(
            client_order_id="client-1", broker_order_id="broker-1",
            state=OrderState.FILLED,
            filled_quantity=0.1 if field == "filled_quantity" else Decimal("3"),
            average_price=0.1 if field == "average_price" else Decimal("72000"),
            broker_request_id="request-1",
        )


@pytest.mark.parametrize(
    "non_finite",
    [
        "NaN",
        "Infinity",
        "-Infinity",
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_trade_signal_rejects_non_finite_string_and_decimal_weights(
    non_finite: object,
) -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="finite"):
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
            target_weight=non_finite,
            raw_payload_hash="a" * 64,
            trace_id=uuid4(),
        )


@pytest.mark.parametrize("field", ["quantity", "limit_price"])
@pytest.mark.parametrize(
    "non_finite",
    [
        "NaN",
        "Infinity",
        "-Infinity",
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_execution_intent_rejects_non_finite_string_and_decimal_values(
    field: str, non_finite: object
) -> None:
    values: dict[str, object] = {
        "quantity": Decimal("3"),
        "limit_price": Decimal("72000"),
    }
    values[field] = non_finite

    with pytest.raises(ValidationError, match="finite"):
        ExecutionIntent(
            intent_id=uuid4(),
            account_id=uuid4(),
            signal_id=uuid4(),
            target_version=1,
            market="KR",
            symbol="005930",
            side=OrderSide.BUY,
            quantity=values["quantity"],
            limit_price=values["limit_price"],
            currency="KRW",
            expires_at=datetime.now(UTC),
            idempotency_key="f" * 64,
        )


@pytest.mark.parametrize("field", ["filled_quantity", "average_price"])
@pytest.mark.parametrize(
    "non_finite",
    [
        "NaN",
        "Infinity",
        "-Infinity",
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_broker_result_rejects_non_finite_string_and_decimal_values(
    field: str, non_finite: object
) -> None:
    values: dict[str, object] = {
        "filled_quantity": Decimal("3"),
        "average_price": Decimal("72000"),
    }
    values[field] = non_finite

    with pytest.raises(ValidationError, match="finite"):
        BrokerOrderResult(
            client_order_id="client-1",
            broker_order_id="broker-1",
            state=OrderState.FILLED,
            filled_quantity=values["filled_quantity"],
            average_price=values["average_price"],
            broker_request_id="request-1",
        )


@pytest.mark.parametrize("field", ["quantity", "limit_price"])
@pytest.mark.parametrize(
    "outside_numeric",
    [
        "1000000000000000000",
        Decimal("1000000000000000000"),
        "0.00000000001",
        Decimal("0.00000000001"),
    ],
)
def test_execution_intent_rejects_values_outside_numeric_28_10(
    field: str, outside_numeric: object
) -> None:
    values: dict[str, object] = {
        "quantity": Decimal("3"),
        "limit_price": Decimal("72000"),
    }
    values[field] = outside_numeric

    with pytest.raises(ValidationError, match=r"NUMERIC\(28,10\)"):
        ExecutionIntent(
            intent_id=uuid4(),
            account_id=uuid4(),
            signal_id=uuid4(),
            target_version=1,
            market="KR",
            symbol="005930",
            side=OrderSide.BUY,
            quantity=values["quantity"],
            limit_price=values["limit_price"],
            currency="KRW",
            expires_at=datetime.now(UTC),
            idempotency_key="f" * 64,
        )


@pytest.mark.parametrize("field", ["filled_quantity", "average_price"])
@pytest.mark.parametrize(
    "outside_numeric",
    [
        "1000000000000000000",
        Decimal("1000000000000000000"),
        "0.00000000001",
        Decimal("0.00000000001"),
    ],
)
def test_broker_result_rejects_values_outside_numeric_28_10(
    field: str, outside_numeric: object
) -> None:
    values: dict[str, object] = {
        "filled_quantity": Decimal("3"),
        "average_price": Decimal("72000"),
    }
    values[field] = outside_numeric

    with pytest.raises(ValidationError, match=r"NUMERIC\(28,10\)"):
        BrokerOrderResult(
            client_order_id="client-1",
            broker_order_id="broker-1",
            state=OrderState.FILLED,
            filled_quantity=values["filled_quantity"],
            average_price=values["average_price"],
            broker_request_id="request-1",
        )


def test_order_models_accept_exact_numeric_28_10_boundaries() -> None:
    maximum = Decimal("999999999999999999.9999999999")
    intent = ExecutionIntent(
        intent_id=uuid4(),
        account_id=uuid4(),
        signal_id=uuid4(),
        target_version=1,
        market="KR",
        symbol="005930",
        side=OrderSide.BUY,
        quantity=maximum,
        limit_price=maximum,
        currency="KRW",
        expires_at=datetime.now(UTC),
        idempotency_key="f" * 64,
    )
    result = BrokerOrderResult(
        client_order_id=intent.idempotency_key,
        broker_order_id="broker-1",
        state=OrderState.FILLED,
        filled_quantity=maximum,
        average_price=maximum,
        broker_request_id="request-1",
    )

    assert intent.quantity == maximum
    assert intent.limit_price == maximum
    assert result.filled_quantity == maximum
    assert result.average_price == maximum


@pytest.mark.parametrize("invalid_price", [Decimal("0"), "0", Decimal("-1"), "-1"])
def test_broker_result_rejects_non_positive_average_price(invalid_price: object) -> None:
    with pytest.raises(ValidationError, match="average_price must be positive"):
        BrokerOrderResult(
            client_order_id="client-1",
            broker_order_id="broker-1",
            state=OrderState.FILLED,
            filled_quantity=Decimal("1"),
            average_price=invalid_price,
            broker_request_id="request-1",
        )
