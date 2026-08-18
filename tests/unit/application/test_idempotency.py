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
