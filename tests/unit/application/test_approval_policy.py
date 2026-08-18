from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from mtoss.application.approval_policy import ApprovalPolicy
from mtoss.domain.approvals import ApprovalMode, ApprovalPolicyConfig, ApprovalStatus


def test_conditional_auto_requires_manual_above_threshold() -> None:
    config = ApprovalPolicyConfig(
        mode=ApprovalMode.CONDITIONAL, auto_notional_limit=Decimal("100000")
    )
    now = datetime.now(UTC)
    assert (
        ApprovalPolicy().decide(config, Decimal("99999"), now, now + timedelta(seconds=90)).status
        is ApprovalStatus.APPROVED
    )
    assert (
        ApprovalPolicy().decide(config, Decimal("100001"), now, now + timedelta(seconds=90)).status
        is ApprovalStatus.PENDING
    )


def test_expired_request_never_approves() -> None:
    now = datetime.now(UTC)
    config = ApprovalPolicyConfig(mode=ApprovalMode.AUTO, auto_notional_limit=None)
    decision = ApprovalPolicy().decide(config, Decimal("1"), now, now - timedelta(seconds=1))
    assert decision.status is ApprovalStatus.EXPIRED


def test_conditional_mode_rejects_missing_threshold() -> None:
    with pytest.raises(ValidationError):
        ApprovalPolicyConfig(mode=ApprovalMode.CONDITIONAL, auto_notional_limit=None)


@pytest.mark.parametrize("mode", [ApprovalMode.AUTO, ApprovalMode.MANUAL])
def test_policy_config_is_immutable(mode: ApprovalMode) -> None:
    config = ApprovalPolicyConfig(mode=mode, auto_notional_limit=None)
    with pytest.raises(ValidationError):
        config.mode = ApprovalMode.AUTO


def test_policy_rejects_float_or_non_finite_limit() -> None:
    with pytest.raises(ValidationError):
        ApprovalPolicyConfig(mode=ApprovalMode.AUTO, auto_notional_limit=0.1)
    with pytest.raises(ValidationError, match="finite"):
        ApprovalPolicyConfig(mode=ApprovalMode.AUTO, auto_notional_limit=Decimal("NaN"))


def test_policy_requires_aware_timestamps() -> None:
    config = ApprovalPolicyConfig(mode=ApprovalMode.AUTO, auto_notional_limit=None)
    aware = datetime.now(UTC)
    with pytest.raises(ValueError, match="timezone-aware"):
        ApprovalPolicy().decide(config, Decimal("1"), datetime.now(), aware)
    with pytest.raises(ValueError, match="timezone-aware"):
        ApprovalPolicy().decide(config, Decimal("1"), aware, datetime.now())


def test_manual_mode_is_pending_and_limit_boundary_is_auto() -> None:
    now = datetime.now(UTC)
    expiry = now + timedelta(seconds=90)
    assert ApprovalPolicy().decide(
        ApprovalPolicyConfig(mode=ApprovalMode.MANUAL, auto_notional_limit=None),
        Decimal("1"), now, expiry
    ).status is ApprovalStatus.PENDING
    assert ApprovalPolicy().decide(
        ApprovalPolicyConfig(mode=ApprovalMode.CONDITIONAL, auto_notional_limit=Decimal("100")),
        Decimal("100"), now, expiry
    ).status is ApprovalStatus.APPROVED
