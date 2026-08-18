from mtoss.domain.enums import OrderState


class InvalidOrderTransition(ValueError):
    pass


ALLOWED: dict[OrderState, frozenset[OrderState]] = {
    OrderState.CREATED: frozenset(
        {OrderState.PENDING_APPROVAL, OrderState.QUEUED, OrderState.REJECTED}
    ),
    OrderState.PENDING_APPROVAL: frozenset(
        {OrderState.QUEUED, OrderState.REJECTED, OrderState.EXPIRED}
    ),
    OrderState.QUEUED: frozenset(
        {OrderState.SUBMITTED, OrderState.REJECTED, OrderState.EXPIRED, OrderState.UNKNOWN}
    ),
    OrderState.SUBMITTED: frozenset(
        {
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCELED,
            OrderState.REJECTED,
            OrderState.UNKNOWN,
        }
    ),
    OrderState.PARTIALLY_FILLED: frozenset(
        {OrderState.FILLED, OrderState.CANCELED, OrderState.UNKNOWN}
    ),
    OrderState.UNKNOWN: frozenset(
        {
            OrderState.SUBMITTED,
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCELED,
            OrderState.REJECTED,
        }
    ),
    OrderState.FILLED: frozenset(),
    OrderState.CANCELED: frozenset(),
    OrderState.REJECTED: frozenset(),
    OrderState.EXPIRED: frozenset(),
}


def transition(current: OrderState, target: OrderState) -> OrderState:
    if target not in ALLOWED[current]:
        raise InvalidOrderTransition(f"cannot transition {current.value} -> {target.value}")
    return target
