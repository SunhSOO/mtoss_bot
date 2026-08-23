"""헤징 계좌 흉내 — 주문 하나가 포지션 하나가 되고 각자 SL/TP를 갖는다."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from mtoss.domain.enums import OrderSide, OrderType
from mtoss.domain.orders import ExecutionIntent
from mtoss.infrastructure.broker.fake import FakeBroker

ACCOUNT = uuid4()
EXPIRES = datetime.now(UTC) + timedelta(hours=1)


def intent(key_seed: str, **overrides: Any) -> ExecutionIntent:
    payload: dict[str, Any] = {
        "intent_id": uuid4(),
        "account_id": ACCOUNT,
        "signal_id": uuid4(),
        "target_version": 1,
        "market": "FX",
        "symbol": "XAUUSD",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "quantity": Decimal("1"),
        "limit_price": None,
        "reference_price": Decimal("4000"),
        "stop_loss": Decimal("3980"),
        "currency": "USD",
        "expires_at": EXPIRES,
        "idempotency_key": key_seed * 64,
    }
    payload.update(overrides)
    return ExecutionIntent(**payload)


async def open_two_tranches(broker: FakeBroker) -> tuple[str, str]:
    await broker.submit(intent("a", tranche_ref="T1", take_profit=Decimal("4020")))
    await broker.submit(intent("b", tranche_ref="T2"))
    positions = await broker.list_positions(ACCOUNT)
    by_role = {item.tranche_ref: item.position_ref for item in positions}
    return by_role["T1"], by_role["T2"]


async def test_each_order_opens_its_own_position() -> None:
    broker = FakeBroker()
    await open_two_tranches(broker)

    positions = await broker.list_positions(ACCOUNT)
    assert len(positions) == 2
    assert {item.tranche_ref for item in positions} == {"T1", "T2"}


async def test_tranches_carry_independent_brackets() -> None:
    """넷팅이면 불가능한 부분이다. 러너는 익절이 없고 주문①만 갖는다."""
    broker = FakeBroker()
    await open_two_tranches(broker)

    positions = {item.tranche_ref: item for item in await broker.list_positions(ACCOUNT)}
    assert positions["T1"].take_profit == Decimal("4020")
    assert positions["T2"].take_profit is None
    assert positions["T1"].stop_loss == positions["T2"].stop_loss == Decimal("3980")


async def test_breakeven_move_touches_only_the_runner() -> None:
    broker = FakeBroker()
    fixed_ref, runner_ref = await open_two_tranches(broker)

    await broker.modify_position_sltp(ACCOUNT, runner_ref, Decimal("4000"), None)

    positions = {item.tranche_ref: item for item in await broker.list_positions(ACCOUNT)}
    assert positions["T2"].stop_loss == Decimal("4000")
    assert positions["T1"].stop_loss == Decimal("3980")


async def test_closing_the_runner_leaves_the_fixed_tranche_open() -> None:
    broker = FakeBroker()
    _, runner_ref = await open_two_tranches(broker)

    result = await broker.close_position(ACCOUNT, runner_ref)

    assert result.filled_quantity == Decimal("1")
    remaining = await broker.list_positions(ACCOUNT)
    assert [item.tranche_ref for item in remaining] == ["T1"]


async def test_partial_close_reduces_the_position() -> None:
    broker = FakeBroker()
    await broker.submit(intent("c", quantity=Decimal("2"), tranche_ref="T1"))
    (position,) = await broker.list_positions(ACCOUNT)

    await broker.close_position(ACCOUNT, position.position_ref, Decimal("1"))

    (remaining,) = await broker.list_positions(ACCOUNT)
    assert remaining.quantity == Decimal("1")


async def test_closing_more_than_held_is_rejected() -> None:
    broker = FakeBroker()
    await broker.submit(intent("d", tranche_ref="T1"))
    (position,) = await broker.list_positions(ACCOUNT)

    with pytest.raises(ValueError, match="cannot close more"):
        await broker.close_position(ACCOUNT, position.position_ref, Decimal("5"))


async def test_unknown_position_is_rejected() -> None:
    broker = FakeBroker()
    with pytest.raises(KeyError):
        await broker.modify_position_sltp(ACCOUNT, "nope", Decimal("1"), None)


async def test_positions_are_scoped_to_the_account() -> None:
    broker = FakeBroker()
    await broker.submit(intent("e", tranche_ref="T1"))

    assert await broker.list_positions(UUID(int=0)) == ()


async def test_resubmitting_the_same_key_does_not_open_a_second_position() -> None:
    broker = FakeBroker()
    duplicate = intent("f", tranche_ref="T1")
    await broker.submit(duplicate)
    await broker.submit(duplicate)

    assert len(await broker.list_positions(ACCOUNT)) == 1


async def test_reduce_only_orders_do_not_open_positions() -> None:
    broker = FakeBroker()
    await broker.submit(
        intent("0", reduce_only=True, stop_loss=None, tranche_ref="T2")
    )

    assert await broker.list_positions(ACCOUNT) == ()
