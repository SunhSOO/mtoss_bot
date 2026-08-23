from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mtoss.domain.enums import OrderSide
from mtoss.infrastructure.broker.mt5_links import (
    COMMENT_LENGTH,
    MAGIC_MASK,
    InMemoryLinkStore,
    Mt5OrderLink,
    comment_for,
    magic_for,
)

ACCOUNT = uuid4()
LOGIN = 87902957


def key(seed: str = "a") -> str:
    return (seed * 64)[:64]


def link(idempotency_key: str | None = None, **overrides: object) -> Mt5OrderLink:
    resolved = idempotency_key or key()
    payload: dict[str, object] = {
        "idempotency_key": resolved,
        "intent_id": uuid4(),
        "account_id": ACCOUNT,
        "mt5_login": LOGIN,
        "magic": overrides.pop("magic", None) or magic_for(key()),
        "broker_symbol": "XAUUSD+",
        "side": OrderSide.BUY,
        "requested_lots": Decimal("0.01"),
        "submit_started_at": datetime.now(UTC),
    }
    payload.update(overrides)
    return Mt5OrderLink(**payload)


def test_magic_fits_63_bits_so_it_survives_a_signed_round_trip() -> None:
    """MT5는 요청에서 ulong으로 받고 조회 때 signed long으로 준다.

    최상위 비트를 비우지 않으면 왕복하며 부호가 뒤집혀 스캔이 실패한다.
    """
    for seed in "0123456789abcdef":
        value = magic_for(key(seed))
        assert 0 <= value <= MAGIC_MASK
        assert value == value & MAGIC_MASK


def test_all_ones_key_does_not_go_negative() -> None:
    assert magic_for("f" * 64) == MAGIC_MASK


def test_magic_is_deterministic() -> None:
    assert magic_for(key("c")) == magic_for(key("c"))


def test_different_keys_give_different_magics() -> None:
    assert magic_for(key("a")) != magic_for(key("b"))


def test_comment_fits_the_broker_limit() -> None:
    """comment는 31자 제한이고 브로커가 [sl] 같은 접미사를 덧붙인다."""
    value = comment_for(key())
    assert len(value) == COMMENT_LENGTH
    assert len(value) + len("[sl]") < 31


def test_link_rejects_a_non_sha256_key() -> None:
    with pytest.raises(ValidationError, match="SHA-256"):
        link("too-short")


def test_magic_for_rejects_a_non_sha256_key() -> None:
    """int(x, 16)이 알아서 터지게 두면 메시지가 불친절하고 원인이 안 보인다."""
    with pytest.raises(ValueError, match="SHA-256"):
        magic_for("too-short")
    with pytest.raises(ValueError, match="SHA-256"):
        magic_for("ZZZZ" * 16)


def test_link_rejects_a_magic_that_would_flip_sign() -> None:
    with pytest.raises(ValidationError, match="63 bits"):
        link(magic=MAGIC_MASK + 1)


def test_link_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        link(submit_started_at=datetime(2026, 1, 1))


def test_link_starts_unresolved() -> None:
    assert link().is_resolved is False


def test_link_is_resolved_once_a_ticket_lands() -> None:
    assert link(order_ticket=555).is_resolved is True


async def test_reserve_is_idempotent_for_the_same_key() -> None:
    """재시도로 같은 키가 다시 와도 새 magic을 발급하면 안 된다."""
    store = InMemoryLinkStore()
    first = await store.reserve(link())
    second = await store.reserve(link(magic=12345))

    assert second.magic == first.magic
    assert len(store.rows) == 1


async def test_magic_collision_raises_instead_of_silently_reusing() -> None:
    store = InMemoryLinkStore()
    await store.reserve(link(key("a")))

    with pytest.raises(ValueError, match="already reserved"):
        await store.reserve(link(key("b"), magic=magic_for(key("a"))))


async def test_missing_row_proves_the_order_was_never_sent() -> None:
    store = InMemoryLinkStore()
    assert await store.get(ACCOUNT, key()) is None


async def test_recording_the_result_marks_the_row_resolved() -> None:
    store = InMemoryLinkStore()
    await store.reserve(link())

    updated = await store.record_result(
        key(), order_ticket=111, deal_ticket=222, position_id=333, retcode=10009
    )

    assert updated.is_resolved
    assert updated.order_ticket == 111
    assert updated.position_id == 333
    assert updated.resolved_at is not None


async def test_recording_an_unknown_key_is_rejected() -> None:
    store = InMemoryLinkStore()
    with pytest.raises(LookupError):
        await store.record_result(
            key(), order_ticket=1, deal_ticket=None, position_id=None, retcode=10009
        )


async def test_rows_are_scoped_to_the_account() -> None:
    store = InMemoryLinkStore()
    await store.reserve(link())
    assert await store.get(uuid4(), key()) is None
