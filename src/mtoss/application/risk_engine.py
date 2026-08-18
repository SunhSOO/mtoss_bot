from decimal import Decimal
from uuid import uuid4

from mtoss.domain.risk import RiskContext, RiskDecision, RiskMetric, RiskRule, RiskViolation

REQUIRED = frozenset(RiskMetric)


class RiskEngine:
    def evaluate(self, context: RiskContext, rules: list[RiskRule]) -> RiskDecision:
        grouped: dict[RiskMetric, list[Decimal]] = {}
        for rule in rules:
            grouped.setdefault(rule.metric, []).append(rule.limit)

        if REQUIRED.difference(grouped):
            return RiskDecision(
                decision_id=uuid4(),
                allowed=False,
                violations=(
                    RiskViolation(
                        code="MISSING_REQUIRED_LIMIT", metric=None, actual=None, limit=None
                    ),
                ),
            )

        actuals = {
            RiskMetric.ORDER_NOTIONAL: context.order_notional,
            RiskMetric.ACCOUNT_CAPITAL: context.account_capital,
            RiskMetric.SYMBOL_WEIGHT: context.resulting_symbol_weight,
            RiskMetric.DAILY_LOSS: context.daily_loss,
            RiskMetric.MAX_DRAWDOWN: context.drawdown,
        }
        violations = tuple(
            RiskViolation(
                code="LIMIT_EXCEEDED", metric=metric, actual=actuals[metric], limit=min(limits)
            )
            for metric, limits in grouped.items()
            if actuals[metric] > min(limits)
        )
        return RiskDecision(decision_id=uuid4(), allowed=not violations, violations=violations)
