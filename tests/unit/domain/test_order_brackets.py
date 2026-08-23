from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mtoss.domain.enums import OrderSide, OrderType
from mtoss.domain.orders import BrokerPosition, ExecutionIntent

KEY = "a" * 64
EXPIRES = datetime.now(UTC) + timedelta(hours=1)


def intent(**overrides: Any) -> ExecutionIntent:
    payload: dict[str, Any] = {
        "intent_id": uuid4(),
        "account_id": uuid4(),
        "signal_id": uuid4(),
        "target_version": 1,
        "market": "FX",
        "symbol": "XAUUSD",
        "side": OrderSide.BUY,
        "quantity": Decimal("1"),
        "limit_price": Decimal("4000"),
        "currency": "USD",
        "expires_at": EXPIRES,
        "idempotency_key": KEY,
    }
    payload.update(overrides)
    return ExecutionIntent(**payload)


def test_limit_orders_still_work_unchanged() -> None:
    order = intent()
    assert order.order_type is OrderType.LIMIT
    assert order.pricing_reference == Decimal("4000")
    assert order.stop_loss is None
    assert order.reduce_only is False


def test_market_order_uses_reference_price_as_the_anchor() -> None:
    """"다음 봉 시가 진입"이 시장가다. 체결가를 미리 알 수 없으니 예상가로 명목을 잡는다."""
    order = intent(
        order_type=OrderType.MARKET, limit_price=None, reference_price=Decimal("4000")
    )
    assert order.pricing_reference == Decimal("4000")


def test_limit_order_without_a_price_is_rejected() -> None:
    with pytest.raises(ValidationError, match="limit orders require limit_price"):
        intent(limit_price=None)


def test_market_order_with_a_limit_price_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not carry a limit_price"):
        intent(order_type=OrderType.MARKET, limit_price=Decimal("4000"))


def test_market_order_without_a_reference_price_is_rejected() -> None:
    with pytest.raises(ValidationError, match="require reference_price"):
        intent(order_type=OrderType.MARKET, limit_price=None)


def test_brackets_ride_along_with_the_order() -> None:
    order = intent(stop_loss=Decimal("3980"), take_profit=Decimal("4020"), tranche_ref="T1")
    assert order.stop_loss == Decimal("3980")
    assert order.take_profit == Decimal("4020")
    assert order.tranche_ref == "T1"


def test_buy_stop_above_the_entry_is_rejected() -> None:
    # 진입가 위의 손절은 즉시 체결되거나 브로커가 거부한다. 실계좌에서만 드러날 버그다.
    with pytest.raises(ValidationError, match="buy stop_loss must sit below"):
        intent(stop_loss=Decimal("4100"))


def test_buy_target_below_the_entry_is_rejected() -> None:
    with pytest.raises(ValidationError, match="buy take_profit must sit above"):
        intent(take_profit=Decimal("3900"))


def test_sell_stop_below_the_entry_is_rejected() -> None:
    with pytest.raises(ValidationError, match="sell stop_loss must sit above"):
        intent(side=OrderSide.SELL, stop_loss=Decimal("3900"))


def test_sell_target_above_the_entry_is_rejected() -> None:
    with pytest.raises(ValidationError, match="sell take_profit must sit below"):
        intent(side=OrderSide.SELL, take_profit=Decimal("4100"))


def test_sell_brackets_on_the_correct_side_are_accepted() -> None:
    order = intent(
        side=OrderSide.SELL, stop_loss=Decimal("4020"), take_profit=Decimal("3980")
    )
    assert order.stop_loss == Decimal("4020")


def test_float_brackets_are_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be a float"):
        intent(stop_loss=3980.0)


def test_non_positive_brackets_are_rejected() -> None:
    with pytest.raises(ValidationError, match="bracket prices must be positive"):
        intent(stop_loss=Decimal("0"))


def test_oversized_tranche_ref_is_rejected() -> None:
    with pytest.raises(ValidationError, match="tranche_ref must be 1-16"):
        intent(tranche_ref="T" * 17)


def test_reduce_only_defaults_to_false() -> None:
    assert intent().reduce_only is False
    assert intent(reduce_only=True).reduce_only is True


def test_broker_position_round_trips() -> None:
    position = BrokerPosition(
        position_ref="123456",
        account_id=uuid4(),
        symbol="XAUUSD",
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        entry_price=Decimal("4000"),
        stop_loss=Decimal("3980"),
        tranche_ref="T2",
        opened_at=EXPIRES,
    )
    assert position.take_profit is None
    assert position.opened_at is not None
    assert position.opened_at.tzinfo is not None


def test_broker_position_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        BrokerPosition(
            position_ref="123456",
            account_id=uuid4(),
            symbol="XAUUSD",
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            entry_price=Decimal("4000"),
            opened_at=datetime(2026, 1, 1),
        )


def test_broker_position_rejects_float_prices() -> None:
    with pytest.raises(ValidationError, match="must not be a float"):
        BrokerPosition(
            position_ref="123456",
            account_id=uuid4(),
            symbol="XAUUSD",
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            entry_price=4000.0,
        )
