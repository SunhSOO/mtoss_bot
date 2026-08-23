"""MT5 리트코드를 우리 주문 상태로 옮긴다.

**이 파일에서 가장 중요한 것은 `AMBIGUOUS_RETCODES`다.** 서버가 주문을 받았는지
알 수 없는 응답을 `REJECTED`로 분류하면 호출자가 재전송하고, 그게 곧 중복주문이다.
그런 코드는 `TimeoutError`로 올려 `ExecutionService`의 재조회 경로를 타게 한다.

리트코드 표: https://www.mql5.com/en/docs/constants/errorswarnings/enum_trade_return_codes
"""

from decimal import Decimal

from mtoss.domain.enums import OrderState
from mtoss.domain.orders import BrokerOrderResult

RETCODE_DONE = 10009
RETCODE_PLACED = 10008
RETCODE_DONE_PARTIAL = 10010

AMBIGUOUS_RETCODES: frozenset[int] = frozenset(
    {
        10011,  # REQUEST_ERROR      요청 처리 중 오류
        10012,  # REQUEST_TIMEOUT    서버가 받았을 수 있다
        10028,  # REQUEST_LOCKED     처리 중 잠김
        10029,  # ORDER_FROZEN       주문이 동결됨
        10031,  # CONNECTION         연결 끊김
    }
)
"""주문이 서버에 도달했는지 **알 수 없는** 코드.

`REJECTED`로 분류하는 순간 중복주문 버그가 된다. `TimeoutError`로 올려서
`ExecutionService`가 재조회 후 `UNKNOWN`으로 확정하게 한다.
"""

RETRY_WITH_OTHER_FILLING = 10030
"""INVALID_FILL. 아무것도 걸리지 않은 것이 보장되므로 다른 필링 모드로 1회 재시도해도 안전하다."""

REJECT_CODES: dict[int, str] = {
    10004: "MT5_REQUOTE",
    10006: "MT5_REJECT",
    10013: "MT5_INVALID_REQUEST",
    10014: "MT5_INVALID_VOLUME",
    10015: "MT5_INVALID_PRICE",
    10016: "MT5_INVALID_STOPS",
    10017: "MT5_TRADE_DISABLED",
    10018: "MT5_MARKET_CLOSED",
    10019: "MT5_NO_MONEY",
    10020: "MT5_PRICE_CHANGED",
    10021: "MT5_PRICE_OFF",
    10022: "MT5_INVALID_EXPIRATION",
    10024: "MT5_TOO_MANY_REQUESTS",
    10026: "MT5_AUTOTRADING_DISABLED_SERVER",
    10027: "MT5_AUTOTRADING_DISABLED_CLIENT",
    10030: "MT5_INVALID_FILL",
    10033: "MT5_LIMIT_ORDERS",
    10034: "MT5_LIMIT_VOLUME",
    10035: "MT5_INVALID_ORDER",
    10036: "MT5_POSITION_CLOSED",
    10038: "MT5_CLOSE_VOLUME_EXCEEDED",
    10039: "MT5_CLOSE_ORDER_EXISTS",
    10040: "MT5_LIMIT_POSITIONS",
    10041: "MT5_REJECT_CANCEL",
    10042: "MT5_LONG_ONLY",
    10043: "MT5_SHORT_ONLY",
    10044: "MT5_CLOSE_ONLY",
    10045: "MT5_FIFO_CLOSE",
}


class Mt5Ambiguous(TimeoutError):
    """주문이 도달했는지 알 수 없다. 절대 재전송하지 말고 재조회할 것."""

    def __init__(self, retcode: int, comment: str = "") -> None:
        super().__init__(f"ambiguous MT5 retcode {retcode}: {comment}")
        self.retcode = retcode
        self.comment = comment


def is_ambiguous(retcode: int) -> bool:
    return retcode in AMBIGUOUS_RETCODES


def resolve_state(retcode: int, requested: Decimal, filled: Decimal) -> OrderState:
    """체결 수량까지 봐야 `FILLED`와 `PARTIALLY_FILLED`가 갈린다."""
    if retcode == RETCODE_PLACED:
        return OrderState.SUBMITTED
    if retcode in (RETCODE_DONE, RETCODE_DONE_PARTIAL):
        if filled <= 0:
            return OrderState.SUBMITTED
        return OrderState.FILLED if filled >= requested else OrderState.PARTIALLY_FILLED
    return OrderState.REJECTED


def error_code_for(retcode: int) -> str | None:
    if retcode in (RETCODE_DONE, RETCODE_PLACED):
        return None
    if retcode == RETCODE_DONE_PARTIAL:
        return "MT5_DONE_PARTIAL"
    return REJECT_CODES.get(retcode, f"MT5_RETCODE_{retcode}")


def build_result(
    *,
    client_order_id: str,
    retcode: int,
    requested_quantity: Decimal,
    filled_quantity: Decimal,
    average_price: Decimal | None,
    broker_order_id: str | None,
    broker_request_id: str | None,
    comment: str = "",
) -> BrokerOrderResult:
    """`order_send` 응답 하나를 우리 결과 모델로 옮긴다.

    모호한 코드는 결과로 만들지 않고 예외로 올린다 — 여기서 `REJECTED`를 만들어
    돌려주면 호출자가 안심하고 재전송해 버린다.
    """
    if is_ambiguous(retcode):
        raise Mt5Ambiguous(retcode, comment)

    state = resolve_state(retcode, requested_quantity, filled_quantity)
    return BrokerOrderResult(
        client_order_id=client_order_id,
        broker_order_id=broker_order_id,
        state=state,
        filled_quantity=filled_quantity,
        average_price=average_price if filled_quantity > 0 else None,
        broker_request_id=broker_request_id,
        error_code=error_code_for(retcode),
    )
