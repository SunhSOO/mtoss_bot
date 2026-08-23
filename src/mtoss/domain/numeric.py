from decimal import Decimal

from mtoss.domain.orders import ORDER_NUMERIC_SCALE

_ORDER_QUANTUM = Decimal(1).scaleb(-ORDER_NUMERIC_SCALE)


def to_order_decimal(value: float) -> Decimal:
    """지표 계산에 쓰인 float를 주문 경계용 Decimal로 옮긴다.

    `Decimal(float)`은 이진 부동소수를 그대로 펼쳐 17자리 넘는 값을 만들고,
    그러면 `validate_order_decimal_input`의 NUMERIC(28,10) 검사에서 걸린다.
    문자열을 거쳐 십진수로 읽은 뒤 소수 10자리로 맞춘다.
    """
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("value must be finite")
    return Decimal(str(value)).quantize(_ORDER_QUANTUM)
