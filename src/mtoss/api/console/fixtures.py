"""Korean sample content for the console stub API.

The data follows section 14 of the UI specification. Values are deterministic:
no randomness and no wall-clock reads, so screenshots stay comparable.
"""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from mtoss.api.console.schemas import (
    AccountSummary,
    ActionResult,
    AdminPayload,
    AdminUserRow,
    ApprovalDetail,
    ApprovalSummary,
    AuditDetail,
    AuditPayload,
    AuditRow,
    AutoTrading,
    ChartSeries,
    ConnectionCheck,
    ConnectionsPayload,
    ConnectionTestResult,
    ControlsPayload,
    CopySourceDetail,
    CopySourceRow,
    DashboardPayload,
    DecisionResult,
    FillRow,
    HealthLevel,
    MetricTile,
    NodeHealth,
    Notice,
    OrderDetail,
    OrderRow,
    OrdersPayload,
    PositionRow,
    RecheckResult,
    ReconciliationRow,
    RiskChangeRow,
    RiskCheck,
    RiskPayload,
    RiskRuleRow,
    Role,
    SeriesPoint,
    SessionPayload,
    StatusInfo,
    StrategyDetail,
    StrategyRow,
    StrategyRunRow,
    StrategySetting,
    TimelineStep,
    Tone,
    TossAccountRow,
    WeightRow,
)
from mtoss.api.console.store import ConsoleStore
from mtoss.application.approval_policy import ApprovalPolicy
from mtoss.domain.approvals import ApprovalMode, ApprovalPolicyConfig, ApprovalStatus
from mtoss.domain.enums import OrderSide, OrderState, SourceType
from mtoss.domain.risk import RiskMetric, RiskScope

KST = timezone(timedelta(hours=9), "KST")
BASE_NOW = datetime(2026, 8, 18, 14, 32, 8, tzinfo=KST)
AS_OF = "2026.08.18 14:32:08 KST"
CLOCK_KST = "14:32:08 KST"
CLOCK_ET = "01:32:08 ET"
BROKER_NOTE = "브로커 확인값 · 2026.08.18 14:32:08 KST"
CONFIRM_PHRASE = "전량 청산 확인"

STATES = (
    "normal",
    "loading",
    "empty",
    "partial",
    "forbidden",
    "server-error",
    "market-data-stale",
    "rate-limited",
    "toss-auth-expired",
    "mt5-offline",
    "strategy-error",
    "emergency-stop",
    "position-mismatch",
)


def normalise_state(value: str | None) -> str:
    if value is None or value not in STATES:
        return "normal"
    return value


def _status(
    level: HealthLevel, label: str, detail: str, as_of: str = CLOCK_KST
) -> StatusInfo:
    return StatusInfo(level=level, label=label, detail=detail, as_of=as_of)


OK = _status("OK", "정상", "모든 점검 통과")
CONNECTED = _status("OK", "연결됨", "8초 전 확인")
WARNED = _status("WARNING", "주의", "확인이 필요합니다")
DISCONNECTED = _status("STOPPED", "연결 끊김", "30초 동안 heartbeat 없음")
EXPIRED_AUTH = _status("ACTION_REQUIRED", "인증 만료", "토스 자격증명 재등록 필요")


def _d(value: str) -> Decimal:
    return Decimal(value)


# --------------------------------------------------------------------------
# 계좌와 노드
# --------------------------------------------------------------------------

ACCOUNT_KR = "acc-toss-kr"
ACCOUNT_US = "acc-toss-us"
ACCOUNT_FX = "acc-mt5-fx"

_ACCOUNT_BASE: tuple[tuple[str, str, str, str, str, str, str, str], ...] = (
    (ACCOUNT_KR, "국내주식 주계좌", "TOSS", "KR", "KRW", "124500000", "1542000", "0.0124"),
    (ACCOUNT_US, "미국주식 장기계좌", "TOSS", "US", "USD", "89213.30", "-731.20", "-0.0082"),
    (ACCOUNT_FX, "MT5 FX 데모", "MT5", "FX", "USD", "12480.55", "64.10", "0.0052"),
)


def build_accounts(store: ConsoleStore, state: str) -> tuple[AccountSummary, ...]:
    rows: list[AccountSummary] = []
    for account_id, alias, broker, market, currency, net, pnl, rate in _ACCOUNT_BASE:
        stopped = account_id in store.stopped_accounts or store.emergency_stop
        status = OK
        if state == "toss-auth-expired" and broker == "TOSS":
            status = EXPIRED_AUTH
            stopped = True
        elif state == "mt5-offline" and broker == "MT5":
            status = _status("STOPPED", "중단됨", "노드 연결 끊김으로 주문 차단")
            stopped = True
        elif state == "market-data-stale":
            status = _status("WARNING", "주의", "시세 지연 2분")
        elif store.emergency_stop or state == "emergency-stop":
            status = _status("STOPPED", "중단됨", "전체 긴급 정지 적용 중")
        elif stopped:
            status = _status("STOPPED", "중단됨", "계좌 주문 정지")
        rows.append(
            AccountSummary(
                account_id=account_id,
                alias=alias,
                broker="TOSS" if broker == "TOSS" else "MT5",
                market="KR" if market == "KR" else ("US" if market == "US" else "FX"),
                currency=currency,
                status=status,
                net_asset=_d(net),
                daily_pnl=_d(pnl),
                daily_pnl_rate=_d(rate),
                order_stopped=stopped,
                confirmed_note=BROKER_NOTE,
            )
        )
    return tuple(rows)


def build_nodes(store: ConsoleStore, state: str) -> tuple[NodeHealth, ...]:
    offline = state == "mt5-offline"
    resumed = "node-seoul-01" in store.resumed_nodes
    primary_status = DISCONNECTED if offline and not resumed else CONNECTED
    if offline and resumed:
        primary_status = _status("WARNING", "연결됨", "사용자 재개 대기 후 복구")
    auto: AutoTrading = "RUNNING"
    if offline and not resumed:
        auto = "STOPPED_BY_OFFLINE"
    if store.emergency_stop or state == "emergency-stop":
        auto = "PAUSED_BY_USER"
    return (
        NodeHealth(
            node_id="node-seoul-01",
            name="MT5 노드 · 서울 데스크",
            account_alias="MT5 FX 데모",
            status=primary_status,
            heartbeat_note="8초 전" if not offline or resumed else "3분 12초 전",
            version="node 1.4.2 / MT5 build 4620",
            last_position_sync="2026.08.18 14:31:58 KST",
            auto_trading=auto,
            pairing_code="MTN-4821-K7Q",
        ),
        NodeHealth(
            node_id="node-home-02",
            name="MT5 노드 · 홈 PC",
            account_alias="MT5 FX 데모 (보조)",
            status=_status("WARNING", "연결 중", "재시도 2회 · 마지막 시도 14:31:40 KST"),
            heartbeat_note="52초 전",
            version="node 1.4.1 / MT5 build 4620",
            last_position_sync="2026.08.18 14:26:04 KST",
            auto_trading="SHADOW",
            pairing_code="MTN-9037-B2M",
        ),
    )


# --------------------------------------------------------------------------
# 승인
# --------------------------------------------------------------------------

_APPROVAL_BASE: tuple[dict[str, str], ...] = (
    {
        "approval_id": "apv-13f-brkb",
        "source_type": "FORM_13F",
        "source_name": "Berkshire Hathaway 13F",
        "account_id": ACCOUNT_US,
        "account_alias": "미국주식 장기계좌",
        "market": "US",
        "symbol": "BRK.B",
        "symbol_name": "버크셔 해서웨이 B",
        "side": "BUY",
        "quantity": "12",
        "current_price": "451.02",
        "signal_price": "448.10",
        "currency": "USD",
        "expires": "84",
        "mode": "MANUAL",
        "current_qty": "0",
        "target_qty": "12",
        "fee": "5.41",
    },
    {
        "approval_id": "apv-leader-005930",
        "source_type": "LEADER",
        "source_name": "내부 리더 A",
        "account_id": ACCOUNT_KR,
        "account_alias": "국내주식 주계좌",
        "market": "KR",
        "symbol": "005930",
        "symbol_name": "삼성전자",
        "side": "BUY",
        "quantity": "30",
        "current_price": "81100",
        "signal_price": "80950",
        "currency": "KRW",
        "expires": "252",
        "mode": "CONDITIONAL",
        "current_qty": "120",
        "target_qty": "150",
        "fee": "3410",
    },
    {
        "approval_id": "apv-ext-msft",
        "source_type": "EXTERNAL",
        "source_name": "Signal Provider Demo",
        "account_id": ACCOUNT_US,
        "account_alias": "미국주식 장기계좌",
        "market": "US",
        "symbol": "MSFT",
        "symbol_name": "마이크로소프트",
        "side": "SELL",
        "quantity": "8",
        "current_price": "463.02",
        "signal_price": "465.40",
        "currency": "USD",
        "expires": "598",
        "mode": "MANUAL",
        "current_qty": "26",
        "target_qty": "18",
        "fee": "3.70",
    },
)


def _expires_label(seconds: int) -> str:
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _approval_summary(raw: dict[str, str], store: ConsoleStore) -> ApprovalSummary:
    approval_id = raw["approval_id"]
    price = _d(raw["current_price"])
    if approval_id in store.approval_rechecked and approval_id == "apv-13f-brkb":
        price = _d("453.88")
    quantity = _d(raw["quantity"])
    status = store.approval_decisions.get(approval_id, ApprovalStatus.PENDING)
    risk_passed = approval_id != "apv-ext-msft"
    risk_note = (
        "위험검사 통과 · 한도 사용률 최대 54%"
        if risk_passed
        else "주의 · 종목 비중 한도 92% 사용"
    )
    return ApprovalSummary(
        approval_id=approval_id,
        source_type=SourceType(raw["source_type"]),
        source_name=raw["source_name"],
        account_id=raw["account_id"],
        account_alias=raw["account_alias"],
        market="KR" if raw["market"] == "KR" else ("US" if raw["market"] == "US" else "FX"),
        symbol=raw["symbol"],
        symbol_name=raw["symbol_name"],
        side=OrderSide(raw["side"]),
        quantity=quantity,
        notional=(price * quantity).quantize(Decimal("0.01")),
        currency=raw["currency"],
        current_price=price,
        signal_price=_d(raw["signal_price"]),
        expires_in_seconds=int(raw["expires"]),
        expires_label=_expires_label(int(raw["expires"])),
        status=status,
        approval_mode=ApprovalMode(raw["mode"]),
        risk_passed=risk_passed,
        risk_note=risk_note,
    )


def build_approvals(store: ConsoleStore, state: str) -> tuple[ApprovalSummary, ...]:
    if state in ("empty", "loading"):
        return ()
    rows = [_approval_summary(raw, store) for raw in _APPROVAL_BASE]
    rows.sort(key=lambda row: row.expires_in_seconds)
    return tuple(rows)


def _risk_checks(approval_id: str) -> tuple[RiskCheck, ...]:
    tight = approval_id == "apv-ext-msft"
    return (
        RiskCheck(
            metric=RiskMetric.ORDER_NOTIONAL,
            scope=RiskScope.ACCOUNT,
            label="1회 주문 금액",
            actual=_d("5412.24"),
            limit=_d("10000"),
            unit="USD",
            usage_percent=_d("54.1"),
            passed=True,
        ),
        RiskCheck(
            metric=RiskMetric.ACCOUNT_CAPITAL,
            scope=RiskScope.ACCOUNT,
            label="계좌 투자금",
            actual=_d("89213.30"),
            limit=_d("120000"),
            unit="USD",
            usage_percent=_d("74.3"),
            passed=True,
        ),
        RiskCheck(
            metric=RiskMetric.SYMBOL_WEIGHT,
            scope=RiskScope.SYMBOL,
            label="종목 비중",
            actual=_d("0.184") if tight else _d("0.061"),
            limit=_d("0.200"),
            unit="비중",
            usage_percent=_d("92.0") if tight else _d("30.5"),
            passed=not tight,
        ),
        RiskCheck(
            metric=RiskMetric.DAILY_LOSS,
            scope=RiskScope.USER,
            label="일일 손실",
            actual=_d("0.0082"),
            limit=_d("0.0300"),
            unit="비율",
            usage_percent=_d("27.3"),
            passed=True,
        ),
        RiskCheck(
            metric=RiskMetric.MAX_DRAWDOWN,
            scope=RiskScope.SYSTEM,
            label="최대 낙폭",
            actual=_d("0.0420"),
            limit=_d("0.1000"),
            unit="비율",
            usage_percent=_d("42.0"),
            passed=True,
        ),
    )


_PORTFOLIO_AFTER = (
    WeightRow(
        symbol="AAPL",
        symbol_name="애플",
        target_weight=_d("0.220"),
        current_weight=_d("0.204"),
    ),
    WeightRow(
        symbol="MSFT",
        symbol_name="마이크로소프트",
        target_weight=_d("0.180"),
        current_weight=_d("0.196"),
    ),
    WeightRow(
        symbol="BRK.B",
        symbol_name="버크셔 해서웨이 B",
        target_weight=_d("0.150"),
        current_weight=_d("0.089"),
    ),
    WeightRow(
        symbol="005930",
        symbol_name="삼성전자",
        target_weight=_d("0.120"),
        current_weight=_d("0.118"),
    ),
)


def find_approval(approval_id: str) -> dict[str, str] | None:
    for raw in _APPROVAL_BASE:
        if raw["approval_id"] == approval_id:
            return raw
    return None


def build_approval_detail(
    approval_id: str, store: ConsoleStore, state: str
) -> ApprovalDetail | None:
    raw = find_approval(approval_id)
    if raw is None:
        return None
    summary = _approval_summary(raw, store)
    notices: list[Notice] = []
    if raw["source_type"] == "FORM_13F":
        notices.append(
            Notice(
                notice_id="n-13f-delay",
                tone="warning",
                title="분기 말 기준 공시이며 최대 45일 지연될 수 있습니다",
                body=(
                    "Berkshire Hathaway · CIK 0001067983 · 2026년 2분기 보고 · "
                    "신고 접수 2026.08.14 · 수정 신고 아님."
                ),
                dismissible=False,
            )
        )
    if not summary.risk_passed:
        notices.append(
            Notice(
                notice_id="n-risk-tight",
                tone="warning",
                title="종목 비중 한도의 92%를 사용합니다",
                body="승인하면 한도까지 여유가 8%만 남습니다. 위험 설정에서 범위를 확인하세요.",
                action_label="위험 설정 열기",
                action_href="/risk",
            )
        )
    if approval_id in store.approval_rechecked and approval_id == "apv-13f-brkb":
        notices.append(
            Notice(
                notice_id="n-recheck",
                tone="critical",
                title="조건이 변경되었습니다",
                body=(
                    "재검사 결과 현재가가 $451.02에서 $453.88로 바뀌었습니다. "
                    "주문은 아직 나가지 않았습니다. 새 값으로 다시 확인해 주세요."
                ),
                dismissible=False,
            )
        )
    if state == "forbidden":
        return None
    return ApprovalDetail(
        summary=summary,
        created_at="2026.08.18 14:30:44 KST",
        expires_at="2026.08.18 14:33:32 KST",
        current_quantity=_d(raw["current_qty"]),
        target_quantity=_d(raw["target_qty"]),
        estimated_fee=_d(raw["fee"]),
        risk_checks=_risk_checks(approval_id),
        portfolio_after=_PORTFOLIO_AFTER,
        notices=tuple(notices),
        decided_reason=store.approval_reasons.get(approval_id),
    )


def recheck_approval(approval_id: str, store: ConsoleStore) -> RecheckResult | None:
    raw = find_approval(approval_id)
    if raw is None:
        return None
    before_price = _d(raw["current_price"])
    quantity = _d(raw["quantity"])
    changed = approval_id == "apv-13f-brkb"
    after_price = _d("453.88") if changed else before_price
    store.approval_rechecked.add(approval_id)
    message = (
        "재검사 결과 현재가와 예상 금액이 변경되었습니다. 주문은 나가지 않았습니다."
        if changed
        else "재검사 결과 조건이 그대로입니다. 승인을 진행할 수 있습니다."
    )
    return RecheckResult(
        approval_id=approval_id,
        changed=changed,
        message=message,
        before_price=before_price,
        after_price=after_price,
        before_notional=(before_price * quantity).quantize(Decimal("0.01")),
        after_notional=(after_price * quantity).quantize(Decimal("0.01")),
    )


def decide_approval(approval_id: str, approve: bool, store: ConsoleStore) -> DecisionResult | None:
    """Run the real ApprovalPolicy, then record the operator decision."""
    raw = find_approval(approval_id)
    if raw is None:
        return None
    quantity = _d(raw["quantity"])
    price = _d(raw["current_price"])
    notional = (price * quantity).quantize(Decimal("0.01"))
    mode = ApprovalMode(raw["mode"])
    limit = _d("2000000") if mode is ApprovalMode.CONDITIONAL else None
    config = ApprovalPolicyConfig(mode=mode, auto_notional_limit=limit)
    expires_at = BASE_NOW + timedelta(seconds=int(raw["expires"]))
    policy_decision = ApprovalPolicy().decide(config, notional, BASE_NOW, expires_at)
    if policy_decision.status is ApprovalStatus.EXPIRED:
        store.approval_decisions[approval_id] = ApprovalStatus.EXPIRED
        store.approval_reasons[approval_id] = "신호가 만료되어 승인할 수 없습니다"
        return DecisionResult(
            approval_id=approval_id,
            status=ApprovalStatus.EXPIRED,
            reason=policy_decision.reason,
            message="신호가 만료되었습니다. 주문은 생성되지 않았습니다.",
        )
    if not approve:
        store.approval_decisions[approval_id] = ApprovalStatus.REJECTED
        store.approval_reasons[approval_id] = "운영자 거절"
        return DecisionResult(
            approval_id=approval_id,
            status=ApprovalStatus.REJECTED,
            reason="operator rejected",
            message="거절했습니다. 주문은 생성되지 않았습니다.",
        )
    store.approval_decisions[approval_id] = ApprovalStatus.APPROVED
    auto = policy_decision.status is ApprovalStatus.APPROVED
    store.approval_reasons[approval_id] = "자동 승인 한도 이내" if auto else "운영자 수동 승인"
    return DecisionResult(
        approval_id=approval_id,
        status=ApprovalStatus.APPROVED,
        reason=policy_decision.reason,
        message="승인했습니다. 주문 계획을 생성해 주문·포지션에서 상태를 확인할 수 있습니다.",
        order_id="ord-plan-0912",
    )


# --------------------------------------------------------------------------
# 주문·체결·포지션
# --------------------------------------------------------------------------

_ORDER_BASE: tuple[dict[str, str], ...] = (
    {
        "order_id": "ord-0871",
        "occurred_at": "2026.08.18 14:31:52 KST",
        "account_id": ACCOUNT_US,
        "account_alias": "미국주식 장기계좌",
        "source_type": "FORM_13F",
        "source_name": "Berkshire Hathaway 13F",
        "market": "US",
        "symbol": "AAPL",
        "symbol_name": "애플",
        "side": "BUY",
        "quantity": "5",
        "filled": "3",
        "average_price": "224.86",
        "currency": "USD",
        "state": "PARTIALLY_FILLED",
        "broker_request_id": "TSS-20260818-000871",
    },
    {
        "order_id": "ord-0864",
        "occurred_at": "2026.08.18 14:28:10 KST",
        "account_id": ACCOUNT_US,
        "account_alias": "미국주식 장기계좌",
        "source_type": "EXTERNAL",
        "source_name": "Signal Provider Demo",
        "market": "US",
        "symbol": "AAPL",
        "symbol_name": "애플",
        "side": "BUY",
        "quantity": "4",
        "filled": "0",
        "average_price": "",
        "currency": "USD",
        "state": "UNKNOWN",
        "broker_request_id": "TSS-20260818-000864",
    },
    {
        "order_id": "ord-0852",
        "occurred_at": "2026.08.18 14:12:44 KST",
        "account_id": ACCOUNT_KR,
        "account_alias": "국내주식 주계좌",
        "source_type": "LEADER",
        "source_name": "내부 리더 A",
        "market": "KR",
        "symbol": "005930",
        "symbol_name": "삼성전자",
        "side": "BUY",
        "quantity": "30",
        "filled": "30",
        "average_price": "81100",
        "currency": "KRW",
        "state": "FILLED",
        "broker_request_id": "TSS-20260818-000852",
    },
    {
        "order_id": "ord-0846",
        "occurred_at": "2026.08.18 13:59:02 KST",
        "account_id": ACCOUNT_KR,
        "account_alias": "국내주식 주계좌",
        "source_type": "STRATEGY",
        "source_name": "S&P 500 변동성 필터",
        "market": "KR",
        "symbol": "000660",
        "symbol_name": "SK하이닉스",
        "side": "SELL",
        "quantity": "12",
        "filled": "0",
        "average_price": "",
        "currency": "KRW",
        "state": "REJECTED",
        "broker_request_id": "TSS-20260818-000846",
    },
    {
        "order_id": "ord-0839",
        "occurred_at": "2026.08.18 13:40:18 KST",
        "account_id": ACCOUNT_FX,
        "account_alias": "MT5 FX 데모",
        "source_type": "STRATEGY",
        "source_name": "USDJPY 1분 추세",
        "market": "FX",
        "symbol": "USDJPY",
        "symbol_name": "미국 달러 / 일본 엔",
        "side": "BUY",
        "quantity": "0.10",
        "filled": "0.10",
        "average_price": "154.284",
        "currency": "USD",
        "state": "FILLED",
        "broker_request_id": "MT5-20260818-004417",
    },
)


def _order_row(raw: dict[str, str]) -> OrderRow:
    average = _d(raw["average_price"]) if raw["average_price"] else None
    return OrderRow(
        order_id=raw["order_id"],
        occurred_at=raw["occurred_at"],
        account_id=raw["account_id"],
        account_alias=raw["account_alias"],
        source_type=SourceType(raw["source_type"]),
        source_name=raw["source_name"],
        market="KR" if raw["market"] == "KR" else ("US" if raw["market"] == "US" else "FX"),
        symbol=raw["symbol"],
        symbol_name=raw["symbol_name"],
        side=OrderSide(raw["side"]),
        quantity=_d(raw["quantity"]),
        filled_quantity=_d(raw["filled"]),
        average_price=average,
        currency=raw["currency"],
        state=OrderState(raw["state"]),
        broker_request_id=raw["broker_request_id"],
    )


_FILLS = (
    FillRow(
        fill_id="fill-1201",
        occurred_at="2026.08.18 14:31:55 KST",
        account_alias="미국주식 장기계좌",
        symbol="AAPL",
        symbol_name="애플",
        side=OrderSide.BUY,
        quantity=_d("3"),
        price=_d("224.86"),
        currency="USD",
        fee=_d("0.34"),
        order_id="ord-0871",
    ),
    FillRow(
        fill_id="fill-1188",
        occurred_at="2026.08.18 14:12:47 KST",
        account_alias="국내주식 주계좌",
        symbol="005930",
        symbol_name="삼성전자",
        side=OrderSide.BUY,
        quantity=_d("30"),
        price=_d("81100"),
        currency="KRW",
        fee=_d("3410"),
        order_id="ord-0852",
    ),
    FillRow(
        fill_id="fill-1170",
        occurred_at="2026.08.18 13:40:19 KST",
        account_alias="MT5 FX 데모",
        symbol="USDJPY",
        symbol_name="미국 달러 / 일본 엔",
        side=OrderSide.BUY,
        quantity=_d("0.10"),
        price=_d("154.284"),
        currency="USD",
        fee=_d("0.70"),
        order_id="ord-0839",
    ),
)

_POSITIONS = (
    PositionRow(
        position_id="pos-005930",
        account_alias="국내주식 주계좌",
        market="KR",
        symbol="005930",
        symbol_name="삼성전자",
        quantity=_d("150"),
        average_price=_d("79420"),
        last_price=_d("81100"),
        currency="KRW",
        unrealised_pnl=_d("252000"),
        weight=_d("0.118"),
        confirmed_note=BROKER_NOTE,
    ),
    PositionRow(
        position_id="pos-000660",
        account_alias="국내주식 주계좌",
        market="KR",
        symbol="000660",
        symbol_name="SK하이닉스",
        quantity=_d("42"),
        average_price=_d("196500"),
        last_price=_d("193200"),
        currency="KRW",
        unrealised_pnl=_d("-138600"),
        weight=_d("0.094"),
        confirmed_note=BROKER_NOTE,
    ),
    PositionRow(
        position_id="pos-aapl",
        account_alias="미국주식 장기계좌",
        market="US",
        symbol="AAPL",
        symbol_name="애플",
        quantity=_d("81"),
        average_price=_d("218.40"),
        last_price=_d("224.86"),
        currency="USD",
        unrealised_pnl=_d("523.26"),
        weight=_d("0.204"),
        confirmed_note=BROKER_NOTE,
    ),
    PositionRow(
        position_id="pos-msft",
        account_alias="미국주식 장기계좌",
        market="US",
        symbol="MSFT",
        symbol_name="마이크로소프트",
        quantity=_d("26"),
        average_price=_d("448.10"),
        last_price=_d("463.02"),
        currency="USD",
        unrealised_pnl=_d("387.92"),
        weight=_d("0.196"),
        confirmed_note=BROKER_NOTE,
    ),
    PositionRow(
        position_id="pos-brkb",
        account_alias="미국주식 장기계좌",
        market="US",
        symbol="BRK.B",
        symbol_name="버크셔 해서웨이 B",
        quantity=_d("17"),
        average_price=_d("442.15"),
        last_price=_d("451.02"),
        currency="USD",
        unrealised_pnl=_d("150.79"),
        weight=_d("0.089"),
        confirmed_note=BROKER_NOTE,
    ),
    PositionRow(
        position_id="pos-usdjpy",
        account_alias="MT5 FX 데모",
        market="FX",
        symbol="USDJPY",
        symbol_name="미국 달러 / 일본 엔",
        quantity=_d("0.30"),
        average_price=_d("153.902"),
        last_price=_d("154.284"),
        currency="USD",
        unrealised_pnl=_d("74.28"),
        weight=_d("0.061"),
        confirmed_note=BROKER_NOTE,
    ),
)

_MISMATCH_ISSUE = ReconciliationRow(
    issue_id="rec-0031",
    detected_at="2026.08.18 14:05:12 KST",
    account_alias="국내주식 주계좌",
    symbol="000660",
    symbol_name="SK하이닉스",
    kind="포지션 불일치",
    internal_value="내부 기록 54주",
    broker_value="브로커 확인 42주",
    status="자동매매 정지",
    guidance="수동 거래로 보입니다. 재동기화를 승인하기 전까지 이 종목 주문이 정지됩니다.",
)

_UNKNOWN_ISSUE = ReconciliationRow(
    issue_id="rec-0029",
    detected_at="2026.08.18 14:28:40 KST",
    account_alias="미국주식 장기계좌",
    symbol="AAPL",
    symbol_name="애플",
    kind="주문 결과 확인 필요",
    internal_value="요청 4주 · 응답 없음",
    broker_value="브로커 조회 진행 중",
    status="확인 필요",
    guidance="같은 주문을 다시 보내지 않고 토스 주문 내역을 확인하고 있습니다.",
)


def build_orders(store: ConsoleStore, state: str) -> OrdersPayload:
    if state in ("empty", "loading"):
        return OrdersPayload(
            orders=(),
            fills=(),
            positions=(),
            reconciliation=(),
            notices=(),
            as_of=AS_OF,
        )
    orders = tuple(_order_row(raw) for raw in _ORDER_BASE)
    issues: tuple[ReconciliationRow, ...] = (_UNKNOWN_ISSUE, _MISMATCH_ISSUE)
    notices: list[Notice] = [
        Notice(
            notice_id="n-unknown",
            tone="warning",
            title="주문 1건의 결과를 확인하고 있습니다",
            body=(
                "주문 요청 후 응답을 받지 못했습니다. 같은 주문을 다시 보내지 않고 "
                "토스 주문 내역을 확인하고 있습니다. 확인될 때까지 이 계좌의 AAPL "
                "주문이 일시정지됩니다."
            ),
            dismissible=False,
        )
    ]
    if state == "rate-limited":
        notices.append(
            Notice(
                notice_id="n-ratelimit",
                tone="warning",
                title="브로커 호출 한도에 도달했습니다",
                body="Retry-After 12초를 따르는 중입니다. 주문 접수는 잠시 늦어질 수 있습니다.",
                dismissible=False,
            )
        )
    if state == "market-data-stale":
        notices.append(
            Notice(
                notice_id="n-stale",
                tone="warning",
                title="시세가 2분 지연되었습니다",
                body="지연된 종목의 전략 실행과 신규 주문을 중단했습니다.",
                dismissible=False,
            )
        )
    return OrdersPayload(
        orders=orders,
        fills=_FILLS,
        positions=_POSITIONS,
        reconciliation=issues,
        notices=tuple(notices),
        as_of=AS_OF,
    )


def build_order_detail(order_id: str, store: ConsoleStore) -> OrderDetail | None:
    raw = next((item for item in _ORDER_BASE if item["order_id"] == order_id), None)
    if raw is None:
        return None
    row = _order_row(raw)
    is_unknown = row.state is OrderState.UNKNOWN
    rechecked = order_id in store.rechecked_orders
    timeline = _timeline_for(row.state, rechecked)
    guidance: Notice | None = None
    if is_unknown:
        guidance = Notice(
            notice_id="n-order-unknown",
            tone="warning",
            title="주문 결과를 확인해야 합니다",
            body=(
                "주문 요청 후 응답을 받지 못했습니다. 같은 주문을 다시 보내지 않습니다. "
                "브로커 상태를 다시 확인해 결과가 정해질 때까지 기다려 주세요."
                + (" 마지막 확인에서도 결과가 정해지지 않았습니다." if rechecked else "")
            ),
            dismissible=False,
        )
    elif row.state is OrderState.REJECTED:
        guidance = Notice(
            notice_id="n-order-rejected",
            tone="critical",
            title="주문이 거절되었습니다",
            body=(
                "브로커가 1회 주문 금액 한도 초과로 거절했습니다. 주문은 체결되지 "
                "않았습니다. 위험 설정에서 한도를 확인한 뒤 다시 신호를 받으세요."
            ),
        )
    return OrderDetail(
        row=row,
        timeline=timeline,
        risk_checks=_risk_checks("ord"),
        approved_by="김운영" if raw["source_type"] != "STRATEGY" else None,
        signal_summary=(
            f"{raw['source_name']} · 목표 비중 신호 · 신호 생성 14:27:58 KST · "
            "trace 8f1c-4d20"
        ),
        intent_summary=(
            f"{raw['symbol']} {raw['side']} {raw['quantity']} · 지정가 주문 · "
            f"멱등키 9c3f…a71b"
        ),
        broker_response=(
            "응답 없음 (timeout 8초) · error_code=AMBIGUOUS_TIMEOUT"
            if is_unknown
            else f"접수 완료 · broker_request_id={raw['broker_request_id']}"
        ),
        reconciliation=(
            "브로커 주문 내역 조회 중 · 재주문하지 않음"
            if is_unknown
            else "내부 기록과 브로커 확인값 일치"
        ),
        can_recheck_broker=is_unknown,
        guidance=guidance,
    )


def _timeline_for(state: OrderState, rechecked: bool) -> tuple[TimelineStep, ...]:
    def step(
        key: str,
        label: str,
        at: str | None,
        status: Literal["DONE", "CURRENT", "PENDING", "BRANCH"],
        note: str | None = None,
    ) -> TimelineStep:
        return TimelineStep(key=key, label=label, at=at, state=status, note=note)

    base = [
        step("created", "생성", "14:27:58 KST", "DONE"),
        step("approved", "승인", "14:28:02 KST", "DONE", "김운영 수동 승인"),
        step("queued", "실행 대기", "14:28:04 KST", "DONE"),
        step("submitted", "브로커 접수", "14:28:10 KST", "DONE"),
    ]
    if state is OrderState.UNKNOWN:
        note = "응답 없음 · 재주문하지 않음"
        if rechecked:
            note = "브로커 재조회 완료 · 결과 아직 미정"
        base.append(step("unknown", "확인 필요", "14:28:18 KST", "BRANCH", note))
        return tuple(base)
    if state is OrderState.REJECTED:
        base.append(step("rejected", "거절", "13:59:04 KST", "BRANCH", "한도 초과"))
        return tuple(base)
    base.append(
        step(
            "partial",
            "부분 체결",
            "14:31:55 KST",
            "CURRENT" if state is OrderState.PARTIALLY_FILLED else "DONE",
            "3/5주 체결" if state is OrderState.PARTIALLY_FILLED else None,
        )
    )
    base.append(
        step(
            "filled",
            "체결",
            "14:12:47 KST" if state is OrderState.FILLED else None,
            "DONE" if state is OrderState.FILLED else "PENDING",
        )
    )
    return tuple(base)


# --------------------------------------------------------------------------
# 전략
# --------------------------------------------------------------------------


def build_strategies(store: ConsoleStore, state: str) -> tuple[StrategyRow, ...]:
    if state in ("empty", "loading"):
        return ()
    error_state = state == "strategy-error"
    return (
        StrategyRow(
            strategy_id="str-usdjpy-trend",
            name="USDJPY 1분 추세",
            version="v1.4.2",
            market="FX",
            timeframe="1분봉",
            account_count=1,
            mode="AUTO",
            last_run_at="2026.08.18 14:32:00 KST",
            status=OK,
            error_count_10d=0,
            paused="str-usdjpy-trend" in store.paused_strategies,
        ),
        StrategyRow(
            strategy_id="str-spx-vol",
            name="S&P 500 변동성 필터",
            version="v0.9.1",
            market="US",
            timeframe="일봉",
            account_count=2,
            mode="SHADOW",
            last_run_at="2026.08.18 05:30:00 KST",
            status=(
                _status("ACTION_REQUIRED", "실패", "전략 오류로 이 전략만 정지")
                if error_state
                else _status("WARNING", "주의", "섀도 모드 운영 중")
            ),
            error_count_10d=7 if error_state else 2,
            paused=error_state or "str-spx-vol" in store.paused_strategies,
        ),
    )


def build_strategy_detail(
    strategy_id: str, store: ConsoleStore, state: str
) -> StrategyDetail | None:
    rows = build_strategies(store, "normal")
    row = next((item for item in rows if item.strategy_id == strategy_id), None)
    if row is None:
        return None
    notices: tuple[Notice, ...] = ()
    if state == "strategy-error" and strategy_id == "str-spx-vol":
        notices = (
            Notice(
                notice_id="n-strategy-error",
                tone="critical",
                title="전략 오류로 이 전략만 정지했습니다",
                body=(
                    "지표 계산에서 데이터 결측이 발생했습니다. 주문은 나가지 않았습니다. "
                    "실행 기록에서 원인을 확인한 뒤 재개하세요."
                ),
                dismissible=False,
            ),
        )
    return StrategyDetail(
        row=row,
        description=(
            "1분봉 추세 추종 전략입니다. 관리자가 배포한 버전만 실행되며 사용자는 "
            "허용된 설정값만 바꿀 수 있습니다."
            if strategy_id == "str-usdjpy-trend"
            else "S&P 500 변동성 구간에서 편입 종목을 축소하는 필터입니다."
        ),
        data_requirements=(
            "1분봉 240개 이상",
            "실시간 호가 스트림",
            "거래시간·휴장일 달력",
        ),
        settings=(
            StrategySetting(
                key="fast_period",
                label="단기 이동평균",
                value="9",
                unit="봉",
                allowed_range="5 ~ 30",
                description="다음 봉부터 적용됩니다.",
            ),
            StrategySetting(
                key="slow_period",
                label="장기 이동평균",
                value="26",
                unit="봉",
                allowed_range="20 ~ 120",
                description="다음 봉부터 적용됩니다.",
            ),
            StrategySetting(
                key="max_position",
                label="최대 포지션",
                value="0.30",
                unit="랏",
                allowed_range="0.01 ~ 1.00",
                description="현재 포지션 0.30랏에 즉시 영향을 줍니다.",
            ),
        ),
        validation=(
            MetricTile(
                key="backtest",
                label="백테스트 기간",
                value="2024.01 ~ 2026.06",
                as_of=AS_OF,
                hint="수수료·슬리피지·휴장일 반영",
            ),
            MetricTile(
                key="shadow",
                label="섀도 운영",
                value="10거래일",
                as_of=AS_OF,
                tone="ok",
                hint="치명적 오류 0건",
            ),
            MetricTile(
                key="determinism",
                label="재현성 검증",
                value="통과",
                as_of=AS_OF,
                tone="ok",
                hint="같은 데이터·설정에서 같은 신호",
            ),
        ),
        runs=(
            StrategyRunRow(
                run_id="run-9921",
                ran_at="2026.08.18 14:32:00 KST",
                signals=1,
                errors=0,
                duration_ms=142,
                note="USDJPY 매수 신호 생성",
            ),
            StrategyRunRow(
                run_id="run-9920",
                ran_at="2026.08.18 14:31:00 KST",
                signals=0,
                errors=0,
                duration_ms=128,
                note="조건 미충족",
            ),
            StrategyRunRow(
                run_id="run-9919",
                ran_at="2026.08.18 14:30:00 KST",
                signals=0,
                errors=1,
                duration_ms=310,
                note="시세 지연으로 건너뜀",
            ),
        ),
        notices=notices,
    )


# --------------------------------------------------------------------------
# 카피트레이딩
# --------------------------------------------------------------------------


def build_copy_sources(store: ConsoleStore, state: str) -> tuple[CopySourceRow, ...]:
    if state in ("empty", "loading"):
        return ()
    return (
        CopySourceRow(
            source_id="cp-leader-a",
            source_type=SourceType.LEADER,
            name="내부 리더 A",
            kind_label="리더 계좌",
            last_signal_at="2026.08.18 14:29:41 KST",
            status=OK,
            subscribed_accounts=("국내주식 주계좌",),
            target_weight=_d("0.35"),
            approval_mode=ApprovalMode.CONDITIONAL,
            drift=_d("0.024"),
            paused="cp-leader-a" in store.paused_sources,
        ),
        CopySourceRow(
            source_id="cp-ext-demo",
            source_type=SourceType.EXTERNAL,
            name="Signal Provider Demo",
            kind_label="외부 신호",
            last_signal_at="2026.08.18 14:18:07 KST",
            status=_status("WARNING", "주의", "중복 신호 2건 차단"),
            subscribed_accounts=("미국주식 장기계좌",),
            target_weight=_d("0.20"),
            approval_mode=ApprovalMode.MANUAL,
            drift=_d("0.008"),
            paused="cp-ext-demo" in store.paused_sources,
        ),
        CopySourceRow(
            source_id="cp-13f-brk",
            source_type=SourceType.FORM_13F,
            name="Berkshire Hathaway",
            kind_label="13F 기관",
            last_signal_at="2026.08.14 09:00:00 KST",
            status=_status("WARNING", "주의", "분기 말 기준 · 최대 45일 지연"),
            subscribed_accounts=("미국주식 장기계좌",),
            target_weight=_d("0.30"),
            approval_mode=ApprovalMode.MANUAL,
            drift=_d("0.051"),
            paused="cp-13f-brk" in store.paused_sources,
        ),
        CopySourceRow(
            source_id="cp-13f-psq",
            source_type=SourceType.FORM_13F,
            name="Pershing Square",
            kind_label="13F 기관",
            last_signal_at="2026.08.12 09:00:00 KST",
            status=_status("WARNING", "주의", "분기 말 기준 · 최대 45일 지연"),
            subscribed_accounts=("미국주식 장기계좌",),
            target_weight=_d("0.15"),
            approval_mode=ApprovalMode.MANUAL,
            drift=_d("0.012"),
            paused="cp-13f-psq" in store.paused_sources,
        ),
    )


_LEADER_WEIGHTS = (
    WeightRow(
        symbol="005930",
        symbol_name="삼성전자",
        target_weight=_d("0.150"),
        current_weight=_d("0.118"),
    ),
    WeightRow(
        symbol="000660",
        symbol_name="SK하이닉스",
        target_weight=_d("0.080"),
        current_weight=_d("0.094"),
    ),
)

_13F_WEIGHTS = (
    WeightRow(
        symbol="AAPL",
        symbol_name="애플",
        target_weight=_d("0.260"),
        current_weight=_d("0.204"),
    ),
    WeightRow(
        symbol="BRK.B",
        symbol_name="버크셔 해서웨이 B",
        target_weight=_d("0.150"),
        current_weight=_d("0.089"),
    ),
    WeightRow(
        symbol="MSFT",
        symbol_name="마이크로소프트",
        target_weight=_d("0.140"),
        current_weight=_d("0.196"),
    ),
)


def build_copy_source_detail(
    source_id: str, store: ConsoleStore, state: str
) -> CopySourceDetail | None:
    row = next(
        (item for item in build_copy_sources(store, "normal") if item.source_id == source_id),
        None,
    )
    if row is None:
        return None
    notices: list[Notice] = []
    weights: tuple[WeightRow, ...] = _LEADER_WEIGHTS
    facts: tuple[StrategySetting, ...] = (
        StrategySetting(key="type", label="소스 유형", value="리더 계좌"),
        StrategySetting(key="sync", label="동기화 방식", value="확인된 포지션 비중"),
        StrategySetting(
            key="note",
            label="주의",
            value="리더 주문 수량이 아니라 목표 비중 차이로 계산합니다.",
        ),
    )
    excluded: tuple[ReconciliationRow, ...] = ()
    if row.source_type is SourceType.FORM_13F:
        weights = _13F_WEIGHTS
        notices.append(
            Notice(
                notice_id="n-13f-quarter",
                tone="warning",
                title="분기 말 기준이며 최대 45일 지연될 수 있습니다",
                body="2026년 2분기 보고 · 신고 접수 2026.08.14 · 수정 신고 아님.",
                dismissible=False,
            )
        )
        facts = (
            StrategySetting(key="cik", label="CIK", value="0001067983"),
            StrategySetting(key="quarter", label="보고 분기", value="2026 Q2"),
            StrategySetting(key="filed", label="신고 접수일", value="2026.08.14"),
            StrategySetting(key="amended", label="수정 신고", value="아니오"),
        )
        excluded = (
            ReconciliationRow(
                issue_id="map-0004",
                detected_at="2026.08.14 09:02:11 KST",
                account_alias="미국주식 장기계좌",
                symbol="OXY WS",
                symbol_name="옥시덴탈 워런트",
                kind="주문 대상 제외",
                internal_value="CUSIP 674599204",
                broker_value="토스 미지원 종목",
                status="제외",
                guidance="옵션·워런트는 리밸런싱 대상에서 제외됩니다.",
            ),
            ReconciliationRow(
                issue_id="map-0007",
                detected_at="2026.08.14 09:02:12 KST",
                account_alias="미국주식 장기계좌",
                symbol="—",
                symbol_name="매핑 실패",
                kind="CUSIP 매핑 실패",
                internal_value="CUSIP 92826C839",
                broker_value="티커 확인 불가",
                status="검토 필요",
                guidance="관리자 검토 후에만 주문 대상에 포함됩니다.",
            ),
        )
    if row.source_type is SourceType.EXTERNAL:
        facts = (
            StrategySetting(key="provider", label="공급자 상태", value="정상"),
            StrategySetting(key="webhook", label="마지막 Webhook", value="14:18:07 KST"),
            StrategySetting(key="signature", label="서명 검증", value="통과 (HMAC-SHA256)"),
            StrategySetting(key="duplicate", label="중복·만료", value="중복 2건 · 만료 1건 차단"),
            StrategySetting(
                key="payload",
                label="원본 페이로드",
                value="관리자 전용 · 비밀값 숨김",
            ),
        )
        weights = ()
    if state == "forbidden":
        return None
    return CopySourceDetail(
        row=row,
        notices=tuple(notices),
        weights=weights,
        excluded=excluded,
        facts=facts,
    )


# --------------------------------------------------------------------------
# 위험 설정
# --------------------------------------------------------------------------

_RISK_BASE: tuple[tuple[str, str, RiskMetric, RiskScope, str, str, str, str, str], ...] = (
    (
        "risk-order-notional",
        "1회 주문 금액",
        RiskMetric.ORDER_NOTIONAL,
        RiskScope.ACCOUNT,
        "계좌 · 국내주식 주계좌",
        "5412000",
        "10000000",
        "KRW",
        "54.1",
    ),
    (
        "risk-account-capital",
        "계좌 투자금",
        RiskMetric.ACCOUNT_CAPITAL,
        RiskScope.ACCOUNT,
        "계좌 · 국내주식 주계좌",
        "124500000",
        "150000000",
        "KRW",
        "83.0",
    ),
    (
        "risk-symbol-weight",
        "종목 비중",
        RiskMetric.SYMBOL_WEIGHT,
        RiskScope.SYMBOL,
        "종목 · MSFT",
        "0.184",
        "0.200",
        "비중",
        "92.0",
    ),
    (
        "risk-daily-loss",
        "일일 손실",
        RiskMetric.DAILY_LOSS,
        RiskScope.USER,
        "사용자 · 김운영",
        "0.0082",
        "0.0300",
        "비율",
        "27.3",
    ),
    (
        "risk-max-drawdown",
        "최대 낙폭",
        RiskMetric.MAX_DRAWDOWN,
        RiskScope.SYSTEM,
        "시스템 전체",
        "0.0420",
        "0.1000",
        "비율",
        "42.0",
    ),
)


def _risk_status(usage: Decimal) -> StatusInfo:
    if usage >= 90:
        return _status("ACTION_REQUIRED", "작업 필요", "한도의 90% 이상 사용")
    if usage >= 70:
        return _status("WARNING", "주의", "한도의 70% 이상 사용")
    return _status("OK", "정상", "한도 여유 있음")


def build_risk(store: ConsoleStore, state: str) -> RiskPayload:
    if state in ("empty", "loading"):
        return RiskPayload(rules=(), history=(), notices=(), as_of=AS_OF)
    rules: list[RiskRuleRow] = []
    for rule_id, name, metric, scope, scope_label, actual, limit, unit, usage in _RISK_BASE:
        effective_limit = store.risk_limits.get(rule_id, limit)
        usage_value = _d(usage)
        if effective_limit != limit and _d(effective_limit) > 0:
            usage_value = (_d(actual) / _d(effective_limit) * 100).quantize(Decimal("0.1"))
        rules.append(
            RiskRuleRow(
                rule_id=rule_id,
                name=name,
                metric=metric,
                scope=scope,
                scope_label=scope_label,
                actual=_d(actual),
                limit=_d(effective_limit),
                unit=unit,
                usage_percent=usage_value,
                status=_risk_status(usage_value),
                changed_by="김운영",
                changed_at="2026.08.17 21:04:33 KST",
            )
        )
    notices: tuple[Notice, ...] = (
        Notice(
            notice_id="n-risk-scope",
            tone="neutral",
            title="한도 변경 규칙",
            body=(
                "더 엄격하게 바꾸면 즉시 적용됩니다. 느슨하게 바꾸려면 재인증이 필요합니다."
            ),
            dismissible=False,
        ),
    )
    return RiskPayload(
        rules=tuple(rules),
        history=(
            RiskChangeRow(
                change_id="chg-0042",
                changed_at="2026.08.17 21:04:33 KST",
                actor="김운영",
                rule_name="종목 비중",
                before="0.250",
                after="0.200",
                direction="TIGHTER",
            ),
            RiskChangeRow(
                change_id="chg-0041",
                changed_at="2026.08.15 10:22:07 KST",
                actor="김운영",
                rule_name="1회 주문 금액",
                before="₩8,000,000",
                after="₩10,000,000",
                direction="LOOSER",
            ),
        ),
        notices=notices,
        as_of=AS_OF,
    )


# --------------------------------------------------------------------------
# 연결
# --------------------------------------------------------------------------

_TOSS_CHECKS_OK = (
    ConnectionCheck(key="scope", label="권한", passed=True, detail="주문·조회 권한 확인"),
    ConnectionCheck(key="accounts", label="계좌 조회", passed=True, detail="2개 계좌 확인"),
    ConnectionCheck(key="quotes", label="시세 조회", passed=True, detail="지연 없음"),
    ConnectionCheck(
        key="orderable",
        label="주문 가능 정보",
        passed=True,
        detail="매수 가능 금액 확인",
    ),
)


def build_connections(store: ConsoleStore, state: str) -> ConnectionsPayload:
    if state in ("empty", "loading"):
        return ConnectionsPayload(
            toss_accounts=(),
            mt5_nodes=(),
            mt5_checks=(),
            notices=(
                Notice(
                    notice_id="n-empty-conn",
                    tone="neutral",
                    title="연결된 계좌가 없습니다",
                    body="토스 계좌를 연결하면 잔고와 주문 상태를 확인할 수 있습니다.",
                    action_label="토스 계좌 연결",
                    action_href="/connections?add=toss",
                ),
            ),
            as_of=AS_OF,
        )
    auth_expired = state == "toss-auth-expired"
    toss_status = EXPIRED_AUTH if auth_expired else CONNECTED
    toss_accounts = (
        TossAccountRow(
            account_id=ACCOUNT_KR,
            alias="국내주식 주계좌",
            market="KR",
            status=toss_status,
            last_sync="2026.08.18 14:31:58 KST",
            secret_note="저장된 비밀값은 다시 표시되지 않습니다.",
            checks=_TOSS_CHECKS_OK,
            order_stopped=ACCOUNT_KR in store.stopped_accounts or auth_expired,
        ),
        TossAccountRow(
            account_id=ACCOUNT_US,
            alias="미국주식 장기계좌",
            market="US",
            status=toss_status,
            last_sync="2026.08.18 14:31:58 KST",
            secret_note="저장된 비밀값은 다시 표시되지 않습니다.",
            checks=_TOSS_CHECKS_OK,
            order_stopped=ACCOUNT_US in store.stopped_accounts or auth_expired,
        ),
    )
    notices: list[Notice] = []
    if auth_expired:
        notices.append(
            Notice(
                notice_id="n-toss-auth",
                tone="critical",
                title="토스 인증이 만료되었습니다",
                body=(
                    "토큰이 만료되어 계좌 조회와 주문이 중단되었습니다. 주문은 나가지 "
                    "않았습니다. 자격증명을 다시 등록하면 재개할 수 있습니다."
                ),
                action_label="자격증명 교체",
                action_href="/connections?rotate=toss",
                dismissible=False,
            )
        )
    if state == "mt5-offline" and "node-seoul-01" not in store.resumed_nodes:
        notices.append(
            Notice(
                notice_id="n-mt5-offline",
                tone="critical",
                title="MT5 노드가 30초 동안 응답하지 않았습니다",
                body=(
                    "해당 계좌의 신규 주문을 차단했습니다. 미체결 주문은 그대로 "
                    "남아 있습니다. 노드 설치 상태를 확인해 주세요."
                ),
                action_label="설치 상태 확인",
                action_href="/connections?node=node-seoul-01",
                dismissible=False,
            )
        )
    mt5_checks = (
        ConnectionCheck(
            key="service",
            label="Windows 서비스",
            passed=state != "mt5-offline",
            detail="자동 시작 등록됨" if state != "mt5-offline" else "서비스 중지됨",
        ),
        ConnectionCheck(key="terminal", label="MT5 터미널", passed=True, detail="build 4620"),
        ConnectionCheck(key="login", label="계정 로그인", passed=True, detail="데모 계정 연결"),
        ConnectionCheck(
            key="market-data",
            label="시장 데이터",
            passed=state not in ("mt5-offline", "market-data-stale"),
            detail="스트림 정상" if state != "market-data-stale" else "2분 지연",
        ),
        ConnectionCheck(
            key="trade",
            label="주문 권한",
            passed=state != "mt5-offline",
            detail="order_send 허용" if state != "mt5-offline" else "노드 offline",
        ),
    )
    return ConnectionsPayload(
        toss_accounts=toss_accounts,
        mt5_nodes=build_nodes(store, state),
        mt5_checks=mt5_checks,
        notices=tuple(notices),
        as_of=AS_OF,
    )


def test_toss_connection(store: ConsoleStore, scenario: str | None) -> ConnectionTestResult:
    store.toss_test_attempts += 1
    failures: dict[str, tuple[str, str]] = {
        "auth": (
            "인증 실패",
            "client ID 또는 secret이 올바르지 않습니다. 값을 다시 확인해 주세요.",
        ),
        "no-account": (
            "계좌 없음",
            "연결 가능한 계좌를 찾지 못했습니다. 토스 앱에서 계좌를 확인하세요.",
        ),
        "terms": (
            "약관 미동의",
            "Open API 이용 약관에 동의해야 계좌를 연결할 수 있습니다.",
        ),
        "rate-limit": (
            "호출 제한",
            "요청이 많아 잠시 제한되었습니다. Retry-After 12초 후 다시 시도하세요.",
        ),
    }
    if scenario in failures:
        title, body = failures[scenario]
        return ConnectionTestResult(
            passed=False,
            code=scenario.upper(),
            title=title,
            body=body,
            checks=(
                ConnectionCheck(
                    key="scope",
                    label="권한",
                    passed=scenario not in ("auth", "terms"),
                    detail="확인 실패" if scenario in ("auth", "terms") else "확인",
                ),
                ConnectionCheck(
                    key="accounts",
                    label="계좌 조회",
                    passed=scenario != "no-account",
                    detail="계좌 없음" if scenario == "no-account" else "확인",
                ),
                ConnectionCheck(key="quotes", label="시세 조회", passed=True, detail="확인"),
                ConnectionCheck(
                    key="orderable",
                    label="주문 가능 정보",
                    passed=scenario != "rate-limit",
                    detail="호출 제한" if scenario == "rate-limit" else "확인",
                ),
            ),
        )
    return ConnectionTestResult(
        passed=True,
        code="OK",
        title="연결 테스트를 통과했습니다",
        body="권한, 계좌 조회, 시세 조회, 주문 가능 정보를 모두 확인했습니다.",
        checks=_TOSS_CHECKS_OK,
    )


# --------------------------------------------------------------------------
# 감사 기록
# --------------------------------------------------------------------------

_AUDIT_ROWS = (
    AuditRow(
        event_id="aud-5521",
        occurred_at="2026.08.18 14:31:52 KST",
        actor="시스템",
        action="주문 접수",
        target="AAPL · 미국주식 장기계좌",
        result="부분 체결 3/5주",
        trace_id="8f1c-4d20",
    ),
    AuditRow(
        event_id="aud-5518",
        occurred_at="2026.08.18 14:28:18 KST",
        actor="시스템",
        action="주문 결과 확인 필요",
        target="AAPL · 미국주식 장기계좌",
        result="UNKNOWN · 재주문 없음",
        trace_id="6b02-91af",
    ),
    AuditRow(
        event_id="aud-5510",
        occurred_at="2026.08.18 14:12:44 KST",
        actor="김운영",
        action="승인",
        target="내부 리더 A · 삼성전자",
        result="승인",
        trace_id="2d77-40c1",
    ),
    AuditRow(
        event_id="aud-5502",
        occurred_at="2026.08.18 13:59:04 KST",
        actor="시스템",
        action="위험검사",
        target="SK하이닉스 · 국내주식 주계좌",
        result="거절 · 1회 주문 금액 초과",
        trace_id="a190-5e33",
    ),
    AuditRow(
        event_id="aud-5490",
        occurred_at="2026.08.17 21:04:33 KST",
        actor="김운영",
        action="위험 한도 변경",
        target="종목 비중 · MSFT",
        result="0.250 → 0.200 (엄격)",
        trace_id="c441-77b8",
    ),
    AuditRow(
        event_id="aud-5486",
        occurred_at="2026.08.17 09:12:00 KST",
        actor="박트레이더",
        action="계좌 연결",
        target="미국주식 장기계좌",
        result="성공",
        trace_id="ee20-1a05",
    ),
)


def build_audit(store: ConsoleStore, state: str) -> AuditPayload:
    if state in ("empty", "loading"):
        return AuditPayload(events=(), notices=(), as_of=AS_OF)
    notices: tuple[Notice, ...] = ()
    if state == "partial":
        notices = (
            Notice(
                notice_id="n-audit-partial",
                tone="warning",
                title="일부 기간의 기록만 불러왔습니다",
                body="최근 24시간만 표시하고 있습니다. 나머지 구간은 다시 시도해 주세요.",
            ),
        )
    return AuditPayload(events=_AUDIT_ROWS, notices=notices, as_of=AS_OF)


def build_audit_detail(event_id: str) -> AuditDetail | None:
    row = next((item for item in _AUDIT_ROWS if item.event_id == event_id), None)
    if row is None:
        return None
    chain = (
        TimelineStep(key="signal", label="신호", at="14:27:58 KST", state="DONE",
                     note="Signal Provider Demo · 목표 비중"),
        TimelineStep(key="risk", label="위험검사", at="14:28:00 KST", state="DONE",
                     note="5개 규칙 통과"),
        TimelineStep(key="approval", label="승인", at="14:28:02 KST", state="DONE",
                     note="김운영 수동 승인"),
        TimelineStep(key="order", label="주문", at="14:28:10 KST", state="DONE",
                     note="브로커 접수"),
        TimelineStep(key="fill", label="체결", at="14:31:55 KST", state="CURRENT",
                     note="부분 체결 3/5주"),
    )
    payload = (
        '{\n  "trace_id": "' + row.trace_id + '",\n  "actor": "' + row.actor + '",\n'
        '  "action": "' + row.action + '",\n  "result": "' + row.result + '",\n'
        '  "secrets": "***"\n}'
    )
    return AuditDetail(row=row, chain=chain, payload_json=payload)


# --------------------------------------------------------------------------
# 관리자와 전체 제어
# --------------------------------------------------------------------------


def build_admin(store: ConsoleStore, state: str) -> AdminPayload:
    return AdminPayload(
        users=(
            AdminUserRow(
                user_id="usr-01",
                name="김운영",
                email="kim.op@example.internal",
                role="ADMIN",
                mfa="TOTP + 패스키",
                last_login="2026.08.18 08:41:02 KST",
                status="활성",
            ),
            AdminUserRow(
                user_id="usr-02",
                name="박트레이더",
                email="park.tr@example.internal",
                role="TRADER",
                mfa="TOTP",
                last_login="2026.08.18 09:12:44 KST",
                status="활성",
            ),
            AdminUserRow(
                user_id="usr-03",
                name="이조회",
                email="lee.view@example.internal",
                role="VIEWER",
                mfa="TOTP",
                last_login="2026.08.17 18:30:10 KST",
                status="활성",
            ),
        ),
        deployments=build_strategies(store, "normal"),
        providers=build_copy_sources(store, "normal"),
        mappings=(
            ReconciliationRow(
                issue_id="map-0007",
                detected_at="2026.08.14 09:02:12 KST",
                account_alias="—",
                symbol="—",
                symbol_name="CUSIP 92826C839",
                kind="CUSIP 매핑 실패",
                internal_value="티커 확인 불가",
                broker_value="토스 종목 없음",
                status="검토 필요",
                guidance="검토 승인 전까지 주문 대상에서 제외됩니다.",
            ),
        ),
        system=(
            MetricTile(key="api", label="API", value="정상", as_of=CLOCK_KST, tone="ok"),
            MetricTile(
                key="db",
                label="PostgreSQL",
                value="스텁 모드",
                as_of=CLOCK_KST,
                tone="warning",
                hint="콘솔 스텁은 DB 없이 동작합니다",
            ),
            MetricTile(
                key="redis",
                label="Redis",
                value="스텁 모드",
                as_of=CLOCK_KST,
                tone="warning",
                hint="콘솔 스텁은 큐를 사용하지 않습니다",
            ),
            MetricTile(key="nodes", label="MT5 노드", value="2대", as_of=CLOCK_KST),
        ),
        notices=(
            Notice(
                notice_id="n-admin-scope",
                tone="neutral",
                title="브로커 비밀값 원문은 조회할 수 없습니다",
                body="관리자도 저장된 자격증명을 다시 볼 수 없으며 교체만 가능합니다.",
                dismissible=False,
            ),
        ),
        as_of=AS_OF,
    )


def build_controls(store: ConsoleStore, state: str) -> ControlsPayload:
    active = store.emergency_stop or state == "emergency-stop"
    total = 4
    done = store.cancel_progress_done if store.emergency_stop else (total if active else 0)
    return ControlsPayload(
        emergency_stop=active,
        stopped_at=store.emergency_stopped_at or ("2026.08.18 14:32:08 KST" if active else None),
        cancel_progress_done=done,
        cancel_progress_total=total,
        liquidation_running=store.liquidation_running,
        liquidation_results=(
            (
                ReconciliationRow(
                    issue_id="liq-0001",
                    detected_at=AS_OF,
                    account_alias="미국주식 장기계좌",
                    symbol="AAPL",
                    symbol_name="애플",
                    kind="청산 주문",
                    internal_value="81주 매도",
                    broker_value="접수",
                    status="진행 중",
                    guidance="시장 상황에 따라 실패할 수 있습니다.",
                ),
                ReconciliationRow(
                    issue_id="liq-0002",
                    detected_at=AS_OF,
                    account_alias="국내주식 주계좌",
                    symbol="005930",
                    symbol_name="삼성전자",
                    kind="청산 주문",
                    internal_value="150주 매도",
                    broker_value="장 마감 · 실패",
                    status="실패",
                    guidance="정규장 재개 후 다시 시도해야 합니다.",
                ),
            )
            if store.liquidation_running
            else ()
        ),
        confirm_phrase=CONFIRM_PHRASE,
        as_of=AS_OF,
    )


def emergency_stop(store: ConsoleStore, reauthenticated: bool) -> ActionResult:
    if not reauthenticated:
        return ActionResult(
            ok=False,
            code="REAUTH_REQUIRED",
            message="전체 긴급 정지는 재인증 후에만 실행할 수 있습니다.",
        )
    store.emergency_stop = True
    store.emergency_stopped_at = AS_OF
    store.cancel_progress_done = 4
    return ActionResult(
        ok=True,
        code="STOPPED",
        message="신규 주문을 차단하고 미체결 주문 4건을 취소했습니다. 포지션은 그대로 유지됩니다.",
    )


def resume_all(store: ConsoleStore) -> ActionResult:
    store.emergency_stop = False
    store.emergency_stopped_at = None
    store.cancel_progress_done = 0
    return ActionResult(ok=True, code="RESUMED", message="전체 긴급 정지를 해제했습니다.")


def liquidate_all(store: ConsoleStore, phrase: str, reauthenticated: bool) -> ActionResult:
    if phrase.strip() != CONFIRM_PHRASE:
        return ActionResult(
            ok=False,
            code="CONFIRM_PHRASE_MISMATCH",
            message=f"확인 문구가 다릅니다. '{CONFIRM_PHRASE}'를 정확히 입력해 주세요.",
        )
    if not reauthenticated:
        return ActionResult(
            ok=False,
            code="REAUTH_REQUIRED",
            message="전량 청산은 MFA 또는 패스키 재인증 후에만 실행할 수 있습니다.",
        )
    store.liquidation_running = True
    return ActionResult(
        ok=True,
        code="LIQUIDATING",
        message="청산 주문을 제출했습니다. 주문별 결과를 아래에서 추적하세요.",
    )


# --------------------------------------------------------------------------
# 세션과 대시보드
# --------------------------------------------------------------------------


def build_session(store: ConsoleStore, state: str, role: str) -> SessionPayload:
    accounts = build_accounts(store, state)
    approvals = build_approvals(store, state)
    pending = sum(1 for item in approvals if item.status is ApprovalStatus.PENDING)
    risk_actions = sum(
        1 for rule in build_risk(store, state).rules if rule.status.level == "ACTION_REQUIRED"
    )
    emergency = store.emergency_stop or state == "emergency-stop"
    if emergency:
        system = _status("STOPPED", "중단됨", "전체 긴급 정지 적용 중")
    elif state in ("server-error", "toss-auth-expired", "mt5-offline"):
        system = _status("ACTION_REQUIRED", "작업 필요", "연결 문제를 확인해 주세요")
    elif state in ("market-data-stale", "rate-limited", "strategy-error", "position-mismatch"):
        system = _status("WARNING", "주의", "일부 기능이 제한되었습니다")
    else:
        system = _status("OK", "정상", "모든 계좌와 노드 정상")
    resolved: Role = "ADMIN"
    if role == "TRADER":
        resolved = "TRADER"
    elif role == "VIEWER":
        resolved = "VIEWER"
    names = {"ADMIN": "김운영", "TRADER": "박트레이더", "VIEWER": "이조회"}
    emails = {
        "ADMIN": "kim.op@example.internal",
        "TRADER": "park.tr@example.internal",
        "VIEWER": "lee.view@example.internal",
    }
    return SessionPayload(
        user_name=names[resolved],
        user_email=emails[resolved],
        role=resolved,
        accounts=accounts,
        system_status=system,
        emergency_stop=emergency,
        kst_time=CLOCK_KST,
        et_time=CLOCK_ET,
        pending_approvals=pending,
        risk_actions=risk_actions,
    )


_NET_ASSET_POINTS = (
    ("08.11", "218420000"),
    ("08.12", "219880000"),
    ("08.13", "217640000"),
    ("08.14", "221300000"),
    ("08.15", "220110000"),
    ("08.16", "220980000"),
    ("08.17", "222640000"),
    ("08.18", "224180000"),
)

_PNL_POINTS = (
    ("08.11", "620000"),
    ("08.12", "1460000"),
    ("08.13", "-2240000"),
    ("08.14", "3660000"),
    ("08.15", "-1190000"),
    ("08.16", "870000"),
    ("08.17", "1660000"),
    ("08.18", "1542000"),
)

_DRAWDOWN_POINTS = (
    ("08.11", "-0.012"),
    ("08.12", "-0.006"),
    ("08.13", "-0.031"),
    ("08.14", "-0.008"),
    ("08.15", "-0.024"),
    ("08.16", "-0.019"),
    ("08.17", "-0.009"),
    ("08.18", "-0.042"),
)


def _series(
    title: str, unit: str, note: str, summary: str, raw: tuple[tuple[str, str], ...]
) -> ChartSeries:
    return ChartSeries(
        title=title,
        unit=unit,
        as_of=AS_OF,
        source_note=note,
        summary=summary,
        points=tuple(SeriesPoint(label=label, value=_d(value)) for label, value in raw),
    )


def build_dashboard(store: ConsoleStore, state: str) -> DashboardPayload:
    accounts = build_accounts(store, state)
    approvals = build_approvals(store, state)
    nodes = build_nodes(store, state)
    risk = build_risk(store, state)
    session = build_session(store, state, "ADMIN")
    healthy = sum(1 for item in accounts if item.status.level == "OK")
    warned = sum(1 for item in accounts if item.status.level == "WARNING")
    stopped = sum(1 for item in accounts if item.status.level in ("STOPPED", "ACTION_REQUIRED"))
    action_rules = tuple(rule for rule in risk.rules if rule.status.level == "ACTION_REQUIRED")
    tiles = (
        MetricTile(
            key="system",
            label="전체 시스템 상태",
            value=session.system_status.label,
            as_of=CLOCK_KST,
            tone=_tone_for(session.system_status.level),
            hint=session.system_status.detail,
        ),
        MetricTile(
            key="accounts",
            label="연결 계좌",
            value=f"정상 {healthy} · 주의 {warned} · 중단 {stopped}",
            as_of=CLOCK_KST,
            tone="ok" if stopped == 0 and warned == 0 else ("critical" if stopped else "warning"),
            hint="계좌 범위 · 전체 내 계좌",
        ),
        MetricTile(
            key="approvals",
            label="승인 대기",
            value=str(session.pending_approvals),
            unit="건",
            as_of=CLOCK_KST,
            tone="warning" if session.pending_approvals else "neutral",
            hint="만료 임박 순으로 정렬됩니다",
        ),
        MetricTile(
            key="risk",
            label="위험 한도 작업 필요",
            value=str(len(action_rules)),
            unit="건",
            as_of=CLOCK_KST,
            tone="critical" if action_rules else "neutral",
            hint=action_rules[0].name if action_rules else "한도 여유 있음",
            usage_percent=action_rules[0].usage_percent if action_rules else None,
        ),
    )
    issues: tuple[ReconciliationRow, ...] = ()
    if state not in ("empty", "loading"):
        issues = (_UNKNOWN_ISSUE, _MISMATCH_ISSUE)
    notices: list[Notice] = []
    if state == "mt5-offline" and "node-seoul-01" not in store.resumed_nodes:
        notices.append(
            Notice(
                notice_id="n-dash-mt5",
                tone="critical",
                title="MT5 노드가 30초 동안 응답하지 않았습니다",
                body="MT5 FX 데모 계좌의 신규 주문을 차단했습니다. 설치 상태를 확인해 주세요.",
                action_label="연결 페이지 열기",
                action_href="/connections",
                dismissible=False,
            )
        )
    if state == "toss-auth-expired":
        notices.append(
            Notice(
                notice_id="n-dash-toss",
                tone="critical",
                title="토스 인증이 만료되었습니다",
                body="계좌 조회와 주문이 중단되었습니다. 자격증명을 다시 등록해 주세요.",
                action_label="연결 페이지 열기",
                action_href="/connections",
                dismissible=False,
            )
        )
    if state == "empty":
        notices.append(
            Notice(
                notice_id="n-dash-empty",
                tone="neutral",
                title="아직 연결된 계좌가 없습니다",
                body="토스 계좌를 연결하고 섀도 모드로 시작하면 이 화면이 채워집니다.",
                action_label="토스 계좌 연결",
                action_href="/connections",
            )
        )
    return DashboardPayload(
        tiles=tiles,
        net_asset=_series(
            "계좌 합산 순자산",
            "KRW",
            BROKER_NOTE,
            "최근 8거래일 순자산은 ₩218,420,000에서 ₩224,180,000으로 늘었습니다.",
            _NET_ASSET_POINTS if state not in ("empty", "loading") else (),
        ),
        daily_pnl=_series(
            "일일 손익",
            "KRW",
            BROKER_NOTE,
            "8거래일 중 5일 수익, 3일 손실입니다. 오늘은 +₩1,542,000입니다.",
            _PNL_POINTS if state not in ("empty", "loading") else (),
        ),
        drawdown=_series(
            "최대 낙폭",
            "비율",
            BROKER_NOTE,
            "최대 낙폭은 −4.2%이며 한도 −10.0% 대비 42%를 사용했습니다.",
            _DRAWDOWN_POINTS if state not in ("empty", "loading") else (),
        ),
        accounts=accounts if state != "empty" else (),
        nodes=nodes if state != "empty" else (),
        approvals=approvals[:3],
        running_sources=build_copy_sources(store, state),
        recent_orders=build_orders(store, state).orders[:4],
        issues=issues,
        notices=tuple(notices),
        as_of=AS_OF,
    )


def _tone_for(level: str) -> Tone:
    if level == "OK":
        return "ok"
    if level == "WARNING":
        return "warning"
    if level == "ACTION_REQUIRED":
        return "critical"
    return "critical"


def utc_base() -> datetime:
    return BASE_NOW.astimezone(UTC)
