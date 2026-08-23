from enum import StrEnum


class SourceType(StrEnum):
    STRATEGY = "STRATEGY"
    LEADER = "LEADER"
    EXTERNAL = "EXTERNAL"
    FORM_13F = "FORM_13F"


class SignalIntent(StrEnum):
    TARGET_WEIGHT = "TARGET_WEIGHT"
    TARGET_QUANTITY = "TARGET_QUANTITY"
    CLOSE = "CLOSE"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    """즉시 체결. "다음 봉 시가 진입"이 이것이다. 체결가는 제출 시점 호가로 정해진다."""

    LIMIT = "LIMIT"
    """지정가로 대기. 체결가는 보장되지만 체결 자체가 보장되지 않는다."""


class OrderState(StrEnum):
    CREATED = "CREATED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    QUEUED = "QUEUED"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"
