// 스텁 API 응답 타입. 금액·수량·비율은 예외 없이 string이다.
// NUMERIC(28,10) 값은 JS number로 왕복할 수 없다.

export type HealthLevel = "OK" | "WARNING" | "ACTION_REQUIRED" | "STOPPED";
export type Tone = "neutral" | "ok" | "warning" | "critical";
export type Broker = "TOSS" | "MT5";
export type Market = "KR" | "US" | "FX";
export type Role = "ADMIN" | "TRADER" | "VIEWER";
export type AutoTrading =
  | "RUNNING"
  | "STOPPED_BY_OFFLINE"
  | "PAUSED_BY_USER"
  | "SHADOW";

export type SourceType = "STRATEGY" | "LEADER" | "EXTERNAL" | "FORM_13F";
export type OrderSide = "BUY" | "SELL";
export type OrderState =
  | "CREATED"
  | "PENDING_APPROVAL"
  | "QUEUED"
  | "SUBMITTED"
  | "PARTIALLY_FILLED"
  | "FILLED"
  | "CANCELED"
  | "REJECTED"
  | "EXPIRED"
  | "UNKNOWN";
export type ApprovalMode = "AUTO" | "MANUAL" | "CONDITIONAL";
export type ApprovalStatus = "APPROVED" | "PENDING" | "REJECTED" | "EXPIRED";
export type RiskScope = "SYSTEM" | "USER" | "ACCOUNT" | "SOURCE" | "SYMBOL";
export type RiskMetric =
  | "ORDER_NOTIONAL"
  | "ACCOUNT_CAPITAL"
  | "SYMBOL_WEIGHT"
  | "DAILY_LOSS"
  | "MAX_DRAWDOWN";

export interface StatusInfo {
  level: HealthLevel;
  label: string;
  detail: string;
  as_of: string;
}

export interface Notice {
  notice_id: string;
  tone: Tone;
  title: string;
  body: string;
  action_label: string | null;
  action_href: string | null;
  dismissible: boolean;
}

export interface MetricTile {
  key: string;
  label: string;
  value: string;
  unit: string | null;
  as_of: string;
  tone: Tone;
  hint: string | null;
  usage_percent: string | null;
}

export interface SeriesPoint {
  label: string;
  value: string;
}

export interface ChartSeries {
  title: string;
  unit: string;
  as_of: string;
  source_note: string;
  summary: string;
  points: SeriesPoint[];
}

export interface WeightRow {
  symbol: string;
  symbol_name: string;
  target_weight: string;
  current_weight: string;
}

export interface AccountSummary {
  account_id: string;
  alias: string;
  broker: Broker;
  market: Market;
  currency: string;
  status: StatusInfo;
  net_asset: string;
  daily_pnl: string;
  daily_pnl_rate: string;
  order_stopped: boolean;
  confirmed_note: string;
}

export interface NodeHealth {
  node_id: string;
  name: string;
  account_alias: string;
  status: StatusInfo;
  heartbeat_note: string;
  version: string;
  last_position_sync: string;
  auto_trading: AutoTrading;
  pairing_code: string;
}

export interface RiskCheck {
  metric: RiskMetric;
  scope: RiskScope;
  label: string;
  actual: string;
  limit: string;
  unit: string;
  usage_percent: string;
  passed: boolean;
}

export interface ApprovalSummary {
  approval_id: string;
  source_type: SourceType;
  source_name: string;
  account_id: string;
  account_alias: string;
  market: Market;
  symbol: string;
  symbol_name: string;
  side: OrderSide;
  quantity: string;
  notional: string;
  currency: string;
  current_price: string;
  signal_price: string;
  expires_in_seconds: number;
  expires_label: string;
  status: ApprovalStatus;
  approval_mode: ApprovalMode;
  risk_passed: boolean;
  risk_note: string;
}

export interface ApprovalDetail {
  summary: ApprovalSummary;
  created_at: string;
  expires_at: string;
  current_quantity: string;
  target_quantity: string;
  estimated_fee: string;
  risk_checks: RiskCheck[];
  portfolio_after: WeightRow[];
  notices: Notice[];
  decided_reason: string | null;
}

export interface RecheckResult {
  approval_id: string;
  changed: boolean;
  message: string;
  before_price: string;
  after_price: string;
  before_notional: string;
  after_notional: string;
}

export interface DecisionResult {
  approval_id: string;
  status: ApprovalStatus;
  reason: string;
  message: string;
  order_id: string | null;
}

export interface TimelineStep {
  key: string;
  label: string;
  at: string | null;
  state: "DONE" | "CURRENT" | "PENDING" | "BRANCH";
  note: string | null;
}

export interface OrderRow {
  order_id: string;
  occurred_at: string;
  account_id: string;
  account_alias: string;
  source_type: SourceType;
  source_name: string;
  market: Market;
  symbol: string;
  symbol_name: string;
  side: OrderSide;
  quantity: string;
  filled_quantity: string;
  average_price: string | null;
  currency: string;
  state: OrderState;
  broker_request_id: string;
}

export interface OrderDetail {
  row: OrderRow;
  timeline: TimelineStep[];
  risk_checks: RiskCheck[];
  approved_by: string | null;
  signal_summary: string;
  intent_summary: string;
  broker_response: string;
  reconciliation: string;
  can_recheck_broker: boolean;
  guidance: Notice | null;
}

export interface FillRow {
  fill_id: string;
  occurred_at: string;
  account_alias: string;
  symbol: string;
  symbol_name: string;
  side: OrderSide;
  quantity: string;
  price: string;
  currency: string;
  fee: string;
  order_id: string;
}

export interface PositionRow {
  position_id: string;
  account_alias: string;
  market: Market;
  symbol: string;
  symbol_name: string;
  quantity: string;
  average_price: string;
  last_price: string;
  currency: string;
  unrealised_pnl: string;
  weight: string;
  confirmed_note: string;
}

export interface ReconciliationRow {
  issue_id: string;
  detected_at: string;
  account_alias: string;
  symbol: string;
  symbol_name: string;
  kind: string;
  internal_value: string;
  broker_value: string;
  status: string;
  guidance: string;
}

export interface OrdersPayload {
  orders: OrderRow[];
  fills: FillRow[];
  positions: PositionRow[];
  reconciliation: ReconciliationRow[];
  notices: Notice[];
  as_of: string;
}

export interface StrategyRow {
  strategy_id: string;
  name: string;
  version: string;
  market: Market;
  timeframe: string;
  account_count: number;
  mode: "SHADOW" | "MANUAL" | "AUTO";
  last_run_at: string;
  status: StatusInfo;
  error_count_10d: number;
  paused: boolean;
}

export interface StrategySetting {
  key: string;
  label: string;
  value: string;
  unit: string | null;
  allowed_range: string;
  description: string;
}

export interface StrategyRunRow {
  run_id: string;
  ran_at: string;
  signals: number;
  errors: number;
  duration_ms: number;
  note: string;
}

export interface StrategyDetail {
  row: StrategyRow;
  description: string;
  data_requirements: string[];
  settings: StrategySetting[];
  validation: MetricTile[];
  runs: StrategyRunRow[];
  notices: Notice[];
}

export interface CopySourceRow {
  source_id: string;
  source_type: SourceType;
  name: string;
  kind_label: string;
  last_signal_at: string;
  status: StatusInfo;
  subscribed_accounts: string[];
  target_weight: string;
  approval_mode: ApprovalMode;
  drift: string;
  paused: boolean;
}

export interface CopySourceDetail {
  row: CopySourceRow;
  notices: Notice[];
  weights: WeightRow[];
  excluded: ReconciliationRow[];
  facts: StrategySetting[];
}

export interface RiskRuleRow {
  rule_id: string;
  name: string;
  metric: RiskMetric;
  scope: RiskScope;
  scope_label: string;
  actual: string;
  limit: string;
  unit: string;
  usage_percent: string;
  status: StatusInfo;
  changed_by: string;
  changed_at: string;
}

export interface RiskChangeRow {
  change_id: string;
  changed_at: string;
  actor: string;
  rule_name: string;
  before: string;
  after: string;
  direction: "TIGHTER" | "LOOSER";
}

export interface RiskPayload {
  rules: RiskRuleRow[];
  history: RiskChangeRow[];
  notices: Notice[];
  as_of: string;
}

export interface ConnectionCheck {
  key: string;
  label: string;
  passed: boolean;
  detail: string;
}

export interface TossAccountRow {
  account_id: string;
  alias: string;
  market: Market;
  status: StatusInfo;
  last_sync: string;
  secret_note: string;
  checks: ConnectionCheck[];
  order_stopped: boolean;
}

export interface ConnectionsPayload {
  toss_accounts: TossAccountRow[];
  mt5_nodes: NodeHealth[];
  mt5_checks: ConnectionCheck[];
  notices: Notice[];
  as_of: string;
}

export interface ConnectionTestResult {
  passed: boolean;
  code: string;
  title: string;
  body: string;
  checks: ConnectionCheck[];
}

export interface AuditRow {
  event_id: string;
  occurred_at: string;
  actor: string;
  action: string;
  target: string;
  result: string;
  trace_id: string;
}

export interface AuditDetail {
  row: AuditRow;
  chain: TimelineStep[];
  payload_json: string;
}

export interface AuditPayload {
  events: AuditRow[];
  notices: Notice[];
  as_of: string;
}

export interface AdminUserRow {
  user_id: string;
  name: string;
  email: string;
  role: Role;
  mfa: string;
  last_login: string;
  status: string;
}

export interface AdminPayload {
  users: AdminUserRow[];
  deployments: StrategyRow[];
  providers: CopySourceRow[];
  mappings: ReconciliationRow[];
  system: MetricTile[];
  notices: Notice[];
  as_of: string;
}

export interface ControlsPayload {
  emergency_stop: boolean;
  stopped_at: string | null;
  cancel_progress_done: number;
  cancel_progress_total: number;
  liquidation_running: boolean;
  liquidation_results: ReconciliationRow[];
  confirm_phrase: string;
  as_of: string;
}

export interface ActionResult {
  ok: boolean;
  code: string;
  message: string;
}

export interface SessionPayload {
  user_name: string;
  user_email: string;
  role: Role;
  accounts: AccountSummary[];
  system_status: StatusInfo;
  emergency_stop: boolean;
  kst_time: string;
  et_time: string;
  pending_approvals: number;
  risk_actions: number;
}

export interface DashboardPayload {
  tiles: MetricTile[];
  net_asset: ChartSeries;
  daily_pnl: ChartSeries;
  drawdown: ChartSeries;
  accounts: AccountSummary[];
  nodes: NodeHealth[];
  approvals: ApprovalSummary[];
  running_sources: CopySourceRow[];
  recent_orders: OrderRow[];
  issues: ReconciliationRow[];
  notices: Notice[];
  as_of: string;
}
