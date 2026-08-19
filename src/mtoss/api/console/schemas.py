"""Response models for the console stub API.

Every monetary or quantity field is serialised as a string so the browser never
turns a NUMERIC(28,10) value into a JavaScript float.
"""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, PlainSerializer

from mtoss.domain.approvals import ApprovalMode, ApprovalStatus
from mtoss.domain.enums import OrderSide, OrderState, SourceType
from mtoss.domain.risk import RiskMetric, RiskScope


def _plain_decimal(value: Decimal) -> str:
    """Render without scientific notation: str(Decimal("1E+7")) would leak "1E+7"."""
    return format(value, "f")


DecimalStr = Annotated[Decimal, PlainSerializer(_plain_decimal, return_type=str)]

HealthLevel = Literal["OK", "WARNING", "ACTION_REQUIRED", "STOPPED"]
Tone = Literal["neutral", "ok", "warning", "critical"]
Broker = Literal["TOSS", "MT5"]
Market = Literal["KR", "US", "FX"]
Role = Literal["ADMIN", "TRADER", "VIEWER"]
AutoTrading = Literal["RUNNING", "STOPPED_BY_OFFLINE", "PAUSED_BY_USER", "SHADOW"]


class ConsoleModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class StatusInfo(ConsoleModel):
    level: HealthLevel
    label: str
    detail: str
    as_of: str


class Notice(ConsoleModel):
    notice_id: str
    tone: Tone
    title: str
    body: str
    action_label: str | None = None
    action_href: str | None = None
    dismissible: bool = True


class MetricTile(ConsoleModel):
    key: str
    label: str
    value: str
    unit: str | None = None
    as_of: str
    tone: Tone = "neutral"
    hint: str | None = None
    usage_percent: DecimalStr | None = None


class SeriesPoint(ConsoleModel):
    label: str
    value: DecimalStr


class ChartSeries(ConsoleModel):
    title: str
    unit: str
    as_of: str
    source_note: str
    summary: str
    points: tuple[SeriesPoint, ...]


class WeightRow(ConsoleModel):
    symbol: str
    symbol_name: str
    target_weight: DecimalStr
    current_weight: DecimalStr


class AccountSummary(ConsoleModel):
    account_id: str
    alias: str
    broker: Broker
    market: Market
    currency: str
    status: StatusInfo
    net_asset: DecimalStr
    daily_pnl: DecimalStr
    daily_pnl_rate: DecimalStr
    order_stopped: bool
    confirmed_note: str


class NodeHealth(ConsoleModel):
    node_id: str
    name: str
    account_alias: str
    status: StatusInfo
    heartbeat_note: str
    version: str
    last_position_sync: str
    auto_trading: AutoTrading
    pairing_code: str


class RiskCheck(ConsoleModel):
    metric: RiskMetric
    scope: RiskScope
    label: str
    actual: DecimalStr
    limit: DecimalStr
    unit: str
    usage_percent: DecimalStr
    passed: bool


class ApprovalSummary(ConsoleModel):
    approval_id: str
    source_type: SourceType
    source_name: str
    account_id: str
    account_alias: str
    market: Market
    symbol: str
    symbol_name: str
    side: OrderSide
    quantity: DecimalStr
    notional: DecimalStr
    currency: str
    current_price: DecimalStr
    signal_price: DecimalStr
    expires_in_seconds: int
    expires_label: str
    status: ApprovalStatus
    approval_mode: ApprovalMode
    risk_passed: bool
    risk_note: str


class ApprovalDetail(ConsoleModel):
    summary: ApprovalSummary
    created_at: str
    expires_at: str
    current_quantity: DecimalStr
    target_quantity: DecimalStr
    estimated_fee: DecimalStr
    risk_checks: tuple[RiskCheck, ...]
    portfolio_after: tuple[WeightRow, ...]
    notices: tuple[Notice, ...]
    decided_reason: str | None = None


class RecheckResult(ConsoleModel):
    approval_id: str
    changed: bool
    message: str
    before_price: DecimalStr
    after_price: DecimalStr
    before_notional: DecimalStr
    after_notional: DecimalStr


class DecisionResult(ConsoleModel):
    approval_id: str
    status: ApprovalStatus
    reason: str
    message: str
    order_id: str | None = None


class TimelineStep(ConsoleModel):
    key: str
    label: str
    at: str | None
    state: Literal["DONE", "CURRENT", "PENDING", "BRANCH"]
    note: str | None = None


class OrderRow(ConsoleModel):
    order_id: str
    occurred_at: str
    account_id: str
    account_alias: str
    source_type: SourceType
    source_name: str
    market: Market
    symbol: str
    symbol_name: str
    side: OrderSide
    quantity: DecimalStr
    filled_quantity: DecimalStr
    average_price: DecimalStr | None
    currency: str
    state: OrderState
    broker_request_id: str


class OrderDetail(ConsoleModel):
    row: OrderRow
    timeline: tuple[TimelineStep, ...]
    risk_checks: tuple[RiskCheck, ...]
    approved_by: str | None
    signal_summary: str
    intent_summary: str
    broker_response: str
    reconciliation: str
    can_recheck_broker: bool
    guidance: Notice | None = None


class FillRow(ConsoleModel):
    fill_id: str
    occurred_at: str
    account_alias: str
    symbol: str
    symbol_name: str
    side: OrderSide
    quantity: DecimalStr
    price: DecimalStr
    currency: str
    fee: DecimalStr
    order_id: str


class PositionRow(ConsoleModel):
    position_id: str
    account_alias: str
    market: Market
    symbol: str
    symbol_name: str
    quantity: DecimalStr
    average_price: DecimalStr
    last_price: DecimalStr
    currency: str
    unrealised_pnl: DecimalStr
    weight: DecimalStr
    confirmed_note: str


class ReconciliationRow(ConsoleModel):
    issue_id: str
    detected_at: str
    account_alias: str
    symbol: str
    symbol_name: str
    kind: str
    internal_value: str
    broker_value: str
    status: str
    guidance: str


class OrdersPayload(ConsoleModel):
    orders: tuple[OrderRow, ...]
    fills: tuple[FillRow, ...]
    positions: tuple[PositionRow, ...]
    reconciliation: tuple[ReconciliationRow, ...]
    notices: tuple[Notice, ...]
    as_of: str


class StrategyRow(ConsoleModel):
    strategy_id: str
    name: str
    version: str
    market: Market
    timeframe: str
    account_count: int
    mode: Literal["SHADOW", "MANUAL", "AUTO"]
    last_run_at: str
    status: StatusInfo
    error_count_10d: int
    paused: bool


class StrategySetting(ConsoleModel):
    key: str
    label: str
    value: str
    unit: str | None = None
    allowed_range: str = ""
    description: str = ""


class StrategyRunRow(ConsoleModel):
    run_id: str
    ran_at: str
    signals: int
    errors: int
    duration_ms: int
    note: str


class StrategyDetail(ConsoleModel):
    row: StrategyRow
    description: str
    data_requirements: tuple[str, ...]
    settings: tuple[StrategySetting, ...]
    validation: tuple[MetricTile, ...]
    runs: tuple[StrategyRunRow, ...]
    notices: tuple[Notice, ...]


class CopySourceRow(ConsoleModel):
    source_id: str
    source_type: SourceType
    name: str
    kind_label: str
    last_signal_at: str
    status: StatusInfo
    subscribed_accounts: tuple[str, ...]
    target_weight: DecimalStr
    approval_mode: ApprovalMode
    drift: DecimalStr
    paused: bool


class CopySourceDetail(ConsoleModel):
    row: CopySourceRow
    notices: tuple[Notice, ...]
    weights: tuple[WeightRow, ...]
    excluded: tuple[ReconciliationRow, ...]
    facts: tuple[StrategySetting, ...]


class RiskRuleRow(ConsoleModel):
    rule_id: str
    name: str
    metric: RiskMetric
    scope: RiskScope
    scope_label: str
    actual: DecimalStr
    limit: DecimalStr
    unit: str
    usage_percent: DecimalStr
    status: StatusInfo
    changed_by: str
    changed_at: str


class RiskChangeRow(ConsoleModel):
    change_id: str
    changed_at: str
    actor: str
    rule_name: str
    before: str
    after: str
    direction: Literal["TIGHTER", "LOOSER"]


class RiskPayload(ConsoleModel):
    rules: tuple[RiskRuleRow, ...]
    history: tuple[RiskChangeRow, ...]
    notices: tuple[Notice, ...]
    as_of: str


class ConnectionCheck(ConsoleModel):
    key: str
    label: str
    passed: bool
    detail: str


class TossAccountRow(ConsoleModel):
    account_id: str
    alias: str
    market: Market
    status: StatusInfo
    last_sync: str
    secret_note: str
    checks: tuple[ConnectionCheck, ...]
    order_stopped: bool


class ConnectionsPayload(ConsoleModel):
    toss_accounts: tuple[TossAccountRow, ...]
    mt5_nodes: tuple[NodeHealth, ...]
    mt5_checks: tuple[ConnectionCheck, ...]
    notices: tuple[Notice, ...]
    as_of: str


class ConnectionTestResult(ConsoleModel):
    passed: bool
    code: str
    title: str
    body: str
    checks: tuple[ConnectionCheck, ...]


class AuditRow(ConsoleModel):
    event_id: str
    occurred_at: str
    actor: str
    action: str
    target: str
    result: str
    trace_id: str


class AuditDetail(ConsoleModel):
    row: AuditRow
    chain: tuple[TimelineStep, ...]
    payload_json: str


class AuditPayload(ConsoleModel):
    events: tuple[AuditRow, ...]
    notices: tuple[Notice, ...]
    as_of: str


class AdminUserRow(ConsoleModel):
    user_id: str
    name: str
    email: str
    role: Role
    mfa: str
    last_login: str
    status: str


class AdminPayload(ConsoleModel):
    users: tuple[AdminUserRow, ...]
    deployments: tuple[StrategyRow, ...]
    providers: tuple[CopySourceRow, ...]
    mappings: tuple[ReconciliationRow, ...]
    system: tuple[MetricTile, ...]
    notices: tuple[Notice, ...]
    as_of: str


class ControlsPayload(ConsoleModel):
    emergency_stop: bool
    stopped_at: str | None
    cancel_progress_done: int
    cancel_progress_total: int
    liquidation_running: bool
    liquidation_results: tuple[ReconciliationRow, ...]
    confirm_phrase: str
    as_of: str


class ActionResult(ConsoleModel):
    ok: bool
    code: str
    message: str


class SessionPayload(ConsoleModel):
    user_name: str
    user_email: str
    role: Role
    accounts: tuple[AccountSummary, ...]
    system_status: StatusInfo
    emergency_stop: bool
    kst_time: str
    et_time: str
    pending_approvals: int
    risk_actions: int


class DashboardPayload(ConsoleModel):
    tiles: tuple[MetricTile, ...]
    net_asset: ChartSeries
    daily_pnl: ChartSeries
    drawdown: ChartSeries
    accounts: tuple[AccountSummary, ...]
    nodes: tuple[NodeHealth, ...]
    approvals: tuple[ApprovalSummary, ...]
    running_sources: tuple[CopySourceRow, ...]
    recent_orders: tuple[OrderRow, ...]
    issues: tuple[ReconciliationRow, ...]
    notices: tuple[Notice, ...]
    as_of: str
