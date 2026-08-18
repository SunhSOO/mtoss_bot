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
