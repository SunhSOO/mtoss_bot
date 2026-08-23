from decimal import Decimal

import pytest

from mtoss.domain.enums import OrderState
from mtoss.domain.orders import BrokerOrderResult
from mtoss.infrastructure.broker.mt5_errors import (
    AMBIGUOUS_RETCODES,
    REJECT_CODES,
    Mt5Ambiguous,
    build_result,
    error_code_for,
    is_ambiguous,
    resolve_state,
)

KEY = "a" * 64


def result(retcode: int, requested: str = "1", filled: str = "1") -> BrokerOrderResult:
    return build_result(
        client_order_id=KEY,
        retcode=retcode,
        requested_quantity=Decimal(requested),
        filled_quantity=Decimal(filled),
        average_price=Decimal("4603.90"),
        broker_order_id="123456",
        broker_request_id="7",
    )


@pytest.mark.parametrize("retcode", sorted(AMBIGUOUS_RETCODES))
def test_ambiguous_retcodes_raise_instead_of_rejecting(retcode: int) -> None:
    """서버가 주문을 받았는지 모르는 응답을 REJECTED로 만들면 호출자가 재전송한다.

    그게 곧 중복주문이므로, 결과를 만들지 않고 예외로 올려 재조회 경로를 태운다.
    """
    with pytest.raises(Mt5Ambiguous):
        result(retcode)


def test_timeout_is_the_ambiguous_case_people_get_wrong() -> None:
    assert is_ambiguous(10012)
    assert is_ambiguous(10031)
    # Mt5Ambiguous는 TimeoutError라서 ExecutionService의 기존 처리기가 그대로 잡는다.
    assert issubclass(Mt5Ambiguous, TimeoutError)


def test_rejections_are_not_ambiguous() -> None:
    for retcode in (10019, 10016, 10018, 10030):
        assert not is_ambiguous(retcode)


def test_full_fill_is_filled() -> None:
    assert resolve_state(10009, Decimal("1"), Decimal("1")) is OrderState.FILLED


def test_short_fill_is_partial() -> None:
    assert resolve_state(10009, Decimal("2"), Decimal("1")) is OrderState.PARTIALLY_FILLED


def test_done_with_no_fill_is_only_submitted() -> None:
    assert resolve_state(10009, Decimal("1"), Decimal("0")) is OrderState.SUBMITTED


def test_placed_is_submitted() -> None:
    assert resolve_state(10008, Decimal("1"), Decimal("0")) is OrderState.SUBMITTED


def test_unknown_retcode_is_rejected_not_accepted() -> None:
    assert resolve_state(19999, Decimal("1"), Decimal("0")) is OrderState.REJECTED


def test_success_carries_no_error_code() -> None:
    assert error_code_for(10009) is None
    assert error_code_for(10008) is None


def test_partial_is_flagged_even_though_it_succeeded() -> None:
    assert error_code_for(10010) == "MT5_DONE_PARTIAL"


def test_known_rejections_get_readable_codes() -> None:
    assert error_code_for(10019) == "MT5_NO_MONEY"
    assert error_code_for(10018) == "MT5_MARKET_CLOSED"
    assert error_code_for(10016) == "MT5_INVALID_STOPS"
    assert error_code_for(10030) == "MT5_INVALID_FILL"


def test_unknown_rejection_keeps_the_number() -> None:
    assert error_code_for(19999) == "MT5_RETCODE_19999"


def test_error_codes_fit_the_database_column() -> None:
    assert all(len(code) <= 128 for code in REJECT_CODES.values())


def test_successful_result_round_trips() -> None:
    built = result(10009)
    assert built.state is OrderState.FILLED
    assert built.client_order_id == KEY
    assert built.error_code is None


def test_rejected_result_drops_the_average_price() -> None:
    built = build_result(
        client_order_id=KEY,
        retcode=10019,
        requested_quantity=Decimal("1"),
        filled_quantity=Decimal("0"),
        average_price=Decimal("4603.90"),
        broker_order_id=None,
        broker_request_id=None,
    )
    assert built.state is OrderState.REJECTED
    assert built.average_price is None
    assert built.error_code == "MT5_NO_MONEY"


def test_invalid_fill_is_a_plain_rejection_so_the_caller_can_retry_the_other_mode() -> None:
    """10030은 아무것도 걸리지 않은 것이 보장되므로 재시도가 안전하다."""
    built = result(10030, filled="0")
    assert built.state is OrderState.REJECTED
    assert built.error_code == "MT5_INVALID_FILL"
