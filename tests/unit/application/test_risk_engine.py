from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mtoss.application.risk_engine import RiskEngine
from mtoss.domain.risk import RiskContext, RiskMetric, RiskRule, RiskScope


def rules(order_limit: str) -> list[RiskRule]:
    return [
        RiskRule(
            rule_id=uuid4(),
            scope=RiskScope.SYSTEM,
            metric=RiskMetric.ORDER_NOTIONAL,
            limit=Decimal("1000000"),
        ),
        RiskRule(
            rule_id=uuid4(),
            scope=RiskScope.ACCOUNT,
            metric=RiskMetric.ORDER_NOTIONAL,
            limit=Decimal(order_limit),
        ),
        RiskRule(
            rule_id=uuid4(),
            scope=RiskScope.ACCOUNT,
            metric=RiskMetric.ACCOUNT_CAPITAL,
            limit=Decimal("5000000"),
        ),
        RiskRule(
            rule_id=uuid4(),
            scope=RiskScope.ACCOUNT,
            metric=RiskMetric.SYMBOL_WEIGHT,
            limit=Decimal("0.20"),
        ),
        RiskRule(
            rule_id=uuid4(),
            scope=RiskScope.ACCOUNT,
            metric=RiskMetric.DAILY_LOSS,
            limit=Decimal("0.03"),
        ),
        RiskRule(
            rule_id=uuid4(),
            scope=RiskScope.ACCOUNT,
            metric=RiskMetric.MAX_DRAWDOWN,
            limit=Decimal("0.10"),
        ),
    ]


def test_more_restrictive_account_limit_wins() -> None:
    context = RiskContext(
        account_id=uuid4(),
        order_notional=Decimal("600000"),
        account_capital=Decimal("5000000"),
        resulting_symbol_weight=Decimal("0.12"),
        daily_loss=Decimal("0.01"),
        drawdown=Decimal("0.02"),
    )
    decision = RiskEngine().evaluate(context, rules("500000"))
    assert decision.allowed is False
    assert decision.violations[0].metric is RiskMetric.ORDER_NOTIONAL


def test_missing_required_metric_fails_closed() -> None:
    context = RiskContext(
        account_id=uuid4(),
        order_notional=Decimal("100"),
        account_capital=Decimal("1000"),
        resulting_symbol_weight=Decimal("0.10"),
        daily_loss=Decimal("0"),
        drawdown=Decimal("0"),
    )
    decision = RiskEngine().evaluate(context, rules("500")[0:1])
    assert decision.allowed is False
    assert {v.code for v in decision.violations} == {"MISSING_REQUIRED_LIMIT"}


def test_risk_models_reject_binary_float() -> None:
    with pytest.raises(ValidationError):
        RiskContext(
            account_id=uuid4(),
            order_notional=0.1,
            account_capital=Decimal("1000"),
            resulting_symbol_weight=Decimal("0.10"),
            daily_loss=Decimal("0"),
            drawdown=Decimal("0"),
        )
    with pytest.raises(ValidationError):
        RiskRule(
            rule_id=uuid4(), scope=RiskScope.SYSTEM, metric=RiskMetric.ORDER_NOTIONAL, limit=0.1
        )
