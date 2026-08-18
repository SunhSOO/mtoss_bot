from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from mtoss.domain.approvals import (
    ApprovalDecision,
    ApprovalMode,
    ApprovalPolicyConfig,
    ApprovalStatus,
)


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _validate_notional(value: Decimal) -> Decimal:
    if isinstance(value, float):
        raise ValueError("order_notional must not be a float")
    try:
        notional = value if isinstance(value, Decimal) else Decimal(value)
    except (TypeError, ValueError):
        raise ValueError("order_notional must be a Decimal, exact string, or integer") from None
    if not notional.is_finite():
        raise ValueError("order_notional must be finite")
    return notional


class ApprovalPolicy:
    def decide(
        self,
        config: ApprovalPolicyConfig,
        order_notional: Decimal,
        now: datetime,
        expires_at: datetime,
    ) -> ApprovalDecision:
        current = _as_utc(now, "now")
        expiry = _as_utc(expires_at, "expires_at")
        notional = _validate_notional(order_notional)
        if current >= expiry:
            return ApprovalDecision(
                approval_id=uuid4(), status=ApprovalStatus.EXPIRED, reason="signal expired"
            )
        if config.mode is ApprovalMode.AUTO:
            return ApprovalDecision(
                approval_id=uuid4(), status=ApprovalStatus.APPROVED, reason="auto policy"
            )
        if (
            config.mode is ApprovalMode.CONDITIONAL
            and config.auto_notional_limit is not None
            and notional <= config.auto_notional_limit
        ):
            return ApprovalDecision(
                approval_id=uuid4(), status=ApprovalStatus.APPROVED, reason="within auto limit"
            )
        return ApprovalDecision(
            approval_id=uuid4(), status=ApprovalStatus.PENDING, reason="manual approval required"
        )
