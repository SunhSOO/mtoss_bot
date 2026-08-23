"""청산 주문은 진입 차단 룰에 막히면 안 된다.

`RiskEngine`은 5개 지표 전부에 룰이 없으면 fail-closed로 거부한다. 그 규칙을 청산에도
그대로 적용하면 일일 손실 한도에 걸린 순간 **손절도 못 내고 포지션에 갇힌다.**
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from mtoss.application.intent_service import (
    CreateIntentCommand,
    IntentService,
    RiskRejected,
)
from mtoss.domain.approvals import ApprovalMode, ApprovalPolicyConfig
from mtoss.domain.enums import OrderSide, OrderState, OrderType
from mtoss.domain.orders import ExecutionIntent
from mtoss.domain.risk import RiskDecision


class RecordingRepository:
    def __init__(self) -> None:
        self.rejections: list[RiskDecision] = []
        self.created: list[tuple[ExecutionIntent, OrderState, dict[str, object]]] = []

    async def record_risk_rejection(
        self, account_id: UUID, signal_id: UUID, decision: RiskDecision
    ) -> None:
        self.rejections.append(decision)

    async def create_with_outbox(
        self,
        intent: ExecutionIntent,
        state: OrderState,
        risk_decision_id: UUID,
        approval_id: UUID,
        risk_snapshot: dict[str, object],
        approval_snapshot: dict[str, object],
    ) -> UUID:
        self.created.append((intent, state, risk_snapshot))
        return intent.intent_id


def command(**overrides: Any) -> CreateIntentCommand:
    payload: dict[str, Any] = {
        "account_id": uuid4(),
        "signal_id": uuid4(),
        "target_version": 1,
        "market": "FX",
        "symbol": "XAUUSD",
        "side": OrderSide.SELL,
        "order_type": OrderType.MARKET,
        "quantity": Decimal("1"),
        "limit_price": None,
        "reference_price": Decimal("4000"),
        "currency": "USD",
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "account_capital": Decimal("389.57"),
        "resulting_symbol_weight": Decimal("0"),
        "daily_loss": Decimal("0"),
        "drawdown": Decimal("0"),
        # 룰이 하나도 없으면 RiskEngine은 MISSING_REQUIRED_LIMIT으로 거부한다.
        "risk_rules": [],
        "approval_config": ApprovalPolicyConfig(mode=ApprovalMode.AUTO, auto_notional_limit=None),
    }
    payload.update(overrides)
    return CreateIntentCommand(**payload)


async def test_entry_is_blocked_when_risk_denies() -> None:
    repository = RecordingRepository()
    service = IntentService(repository)

    with pytest.raises(RiskRejected):
        await service.create(command())

    assert repository.rejections
    assert not repository.created


async def test_reduce_only_order_survives_the_same_denial() -> None:
    repository = RecordingRepository()
    service = IntentService(repository)

    result = await service.create(command(reduce_only=True))

    assert result.state is OrderState.QUEUED
    assert not repository.rejections
    assert repository.created


async def test_reduce_only_still_records_the_violations_for_audit() -> None:
    """통과시키되 조용히 지나가지는 않는다. 감사에서 위반 내역이 보여야 한다."""
    repository = RecordingRepository()
    service = IntentService(repository)

    await service.create(command(reduce_only=True))

    (_, _, snapshot) = repository.created[0]
    assert snapshot["allowed"] is True
    assert snapshot["violations"]


async def test_reduce_only_flag_reaches_the_persisted_intent() -> None:
    repository = RecordingRepository()
    service = IntentService(repository)

    await service.create(command(reduce_only=True, tranche_ref="T2"))

    (intent, _, _) = repository.created[0]
    assert intent.reduce_only is True
    assert intent.tranche_ref == "T2"
    assert intent.order_type is OrderType.MARKET
