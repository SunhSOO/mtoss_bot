"""Console stub API.

Serves the Korean mock data behind the operations console. It never touches
PostgreSQL or Redis, so it runs without Docker. It is mounted only when
`CONSOLE_STUB_ENABLED` is true and is guarded by the same internal key as the
execution routes.

There is deliberately no resubmit endpoint for an order in `UNKNOWN`: the only
action offered is a broker status re-check.
"""

from decimal import Decimal, DecimalException
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from mtoss.api.console import fixtures
from mtoss.api.console.schemas import (
    ActionResult,
    AdminPayload,
    ApprovalDetail,
    ApprovalSummary,
    AuditDetail,
    AuditPayload,
    ConnectionsPayload,
    ConnectionTestResult,
    ControlsPayload,
    CopySourceDetail,
    CopySourceRow,
    DashboardPayload,
    DecisionResult,
    OrderDetail,
    OrdersPayload,
    RecheckResult,
    RiskPayload,
    SessionPayload,
    StrategyDetail,
    StrategyRow,
)
from mtoss.api.console.store import ConsoleStore
from mtoss.api.dependencies import require_internal_key

router = APIRouter(
    prefix="/console/v1",
    tags=["console"],
    dependencies=[Depends(require_internal_key)],
)

StateQuery = Annotated[str | None, Query(description="화면 상태 시뮬레이션")]
RoleQuery = Annotated[str | None, Query(description="역할 시뮬레이션")]


def get_store(request: Request) -> ConsoleStore:
    store = getattr(request.app.state, "console_store", None)
    if not isinstance(store, ConsoleStore):
        raise HTTPException(status_code=503, detail={"code": "CONSOLE_STUB_DISABLED"})
    return store


StoreDep = Annotated[ConsoleStore, Depends(get_store)]


def _guard(state: str) -> None:
    """Turn the simulated failure states into real HTTP failures."""
    if state == "forbidden":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "이 화면을 볼 권한이 없습니다."},
        )
    if state == "server-error":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "SERVER_ERROR", "message": "데이터를 불러오지 못했습니다."},
        )


def _resolve(state: StateQuery) -> str:
    return fixtures.normalise_state(state)


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": what})


# ---------------------------------------------------------------- 세션·대시보드


@router.get("/session")
async def get_session(store: StoreDep, state: StateQuery = None, role: RoleQuery = None) -> (
    SessionPayload
):
    resolved = _resolve(state)
    if resolved == "server-error":
        _guard(resolved)
    return fixtures.build_session(store, resolved, role or "ADMIN")


@router.get("/dashboard")
async def get_dashboard(store: StoreDep, state: StateQuery = None) -> DashboardPayload:
    resolved = _resolve(state)
    _guard(resolved)
    return fixtures.build_dashboard(store, resolved)


# ---------------------------------------------------------------------- 전략


@router.get("/strategies")
async def list_strategies(store: StoreDep, state: StateQuery = None) -> tuple[StrategyRow, ...]:
    resolved = _resolve(state)
    _guard(resolved)
    return fixtures.build_strategies(store, resolved)


@router.get("/strategies/{strategy_id}")
async def get_strategy(
    strategy_id: str, store: StoreDep, state: StateQuery = None
) -> StrategyDetail:
    resolved = _resolve(state)
    _guard(resolved)
    detail = fixtures.build_strategy_detail(strategy_id, store, resolved)
    if detail is None:
        raise _not_found("전략을 찾을 수 없습니다.")
    return detail


@router.post("/strategies/{strategy_id}/toggle")
async def toggle_strategy(strategy_id: str, store: StoreDep) -> ActionResult:
    if strategy_id in store.paused_strategies:
        store.paused_strategies.discard(strategy_id)
        return ActionResult(ok=True, code="RESUMED", message="전략 실행을 재개했습니다.")
    store.paused_strategies.add(strategy_id)
    return ActionResult(
        ok=True,
        code="PAUSED",
        message="전략을 일시정지했습니다. 기존 포지션은 그대로 유지됩니다.",
    )


# ------------------------------------------------------------------ 카피트레이딩


@router.get("/copy-sources")
async def list_copy_sources(
    store: StoreDep, state: StateQuery = None, source_type: str | None = None
) -> tuple[CopySourceRow, ...]:
    resolved = _resolve(state)
    _guard(resolved)
    rows = fixtures.build_copy_sources(store, resolved)
    if source_type:
        rows = tuple(row for row in rows if row.source_type.value == source_type)
    return rows


@router.get("/copy-sources/{source_id}")
async def get_copy_source(
    source_id: str, store: StoreDep, state: StateQuery = None
) -> CopySourceDetail:
    resolved = _resolve(state)
    _guard(resolved)
    detail = fixtures.build_copy_source_detail(source_id, store, resolved)
    if detail is None:
        raise _not_found("신호원을 찾을 수 없습니다.")
    return detail


@router.post("/copy-sources/{source_id}/toggle")
async def toggle_copy_source(source_id: str, store: StoreDep) -> ActionResult:
    if source_id in store.paused_sources:
        store.paused_sources.discard(source_id)
        return ActionResult(ok=True, code="RESUMED", message="신호원 구독을 재개했습니다.")
    store.paused_sources.add(source_id)
    return ActionResult(ok=True, code="PAUSED", message="신호원을 일시정지했습니다.")


# ---------------------------------------------------------------------- 승인함


@router.get("/approvals")
async def list_approvals(
    store: StoreDep, state: StateQuery = None
) -> tuple[ApprovalSummary, ...]:
    resolved = _resolve(state)
    _guard(resolved)
    return fixtures.build_approvals(store, resolved)


@router.get("/approvals/{approval_id}")
async def get_approval(
    approval_id: str, store: StoreDep, state: StateQuery = None
) -> ApprovalDetail:
    resolved = _resolve(state)
    _guard(resolved)
    detail = fixtures.build_approval_detail(approval_id, store, resolved)
    if detail is None:
        raise _not_found("승인 요청을 찾을 수 없습니다.")
    return detail


@router.post("/approvals/{approval_id}/recheck")
async def recheck_approval(approval_id: str, store: StoreDep) -> RecheckResult:
    result = fixtures.recheck_approval(approval_id, store)
    if result is None:
        raise _not_found("승인 요청을 찾을 수 없습니다.")
    return result


class DecisionRequest(BaseModel):
    action: Literal["APPROVE", "REJECT"]
    rechecked: bool = False


@router.post("/approvals/{approval_id}/decide")
async def decide_approval(
    approval_id: str, payload: DecisionRequest, store: StoreDep
) -> DecisionResult:
    if payload.action == "APPROVE" and approval_id not in store.approval_rechecked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "RECHECK_REQUIRED",
                "message": "승인 전에 가격과 계좌 상태를 다시 확인해야 합니다.",
            },
        )
    result = fixtures.decide_approval(approval_id, payload.action == "APPROVE", store)
    if result is None:
        raise _not_found("승인 요청을 찾을 수 없습니다.")
    return result


# ------------------------------------------------------------------ 주문·포지션


@router.get("/orders")
async def get_orders(store: StoreDep, state: StateQuery = None) -> OrdersPayload:
    resolved = _resolve(state)
    _guard(resolved)
    return fixtures.build_orders(store, resolved)


@router.get("/orders/{order_id}")
async def get_order(order_id: str, store: StoreDep, state: StateQuery = None) -> OrderDetail:
    resolved = _resolve(state)
    _guard(resolved)
    detail = fixtures.build_order_detail(order_id, store)
    if detail is None:
        raise _not_found("주문을 찾을 수 없습니다.")
    return detail


@router.post("/orders/{order_id}/recheck-broker")
async def recheck_broker(order_id: str, store: StoreDep) -> ActionResult:
    detail = fixtures.build_order_detail(order_id, store)
    if detail is None:
        raise _not_found("주문을 찾을 수 없습니다.")
    if not detail.can_recheck_broker:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "RECHECK_NOT_APPLICABLE",
                "message": "이 주문은 결과가 이미 정해져 재확인이 필요하지 않습니다.",
            },
        )
    store.rechecked_orders.add(order_id)
    return ActionResult(
        ok=True,
        code="RECHECKED",
        message=(
            "브로커 주문 내역을 다시 조회했습니다. 아직 결과가 정해지지 않았습니다. "
            "같은 주문을 다시 보내지 않습니다."
        ),
    )


# ---------------------------------------------------------------------- 위험 설정


@router.get("/risk-rules")
async def get_risk_rules(store: StoreDep, state: StateQuery = None) -> RiskPayload:
    resolved = _resolve(state)
    _guard(resolved)
    return fixtures.build_risk(store, resolved)


class RiskUpdateRequest(BaseModel):
    limit: str
    reauthenticated: bool = False


@router.patch("/risk-rules/{rule_id}")
async def update_risk_rule(
    rule_id: str, payload: RiskUpdateRequest, store: StoreDep
) -> ActionResult:
    current = next(
        (rule for rule in fixtures.build_risk(store, "normal").rules if rule.rule_id == rule_id),
        None,
    )
    if current is None:
        raise _not_found("위험 규칙을 찾을 수 없습니다.")
    try:
        new_limit = Decimal(payload.limit)
    except (DecimalException, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_LIMIT", "message": "한도는 숫자여야 합니다."},
        ) from exc
    if new_limit > current.limit and not payload.reauthenticated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REAUTH_REQUIRED",
                "message": "한도를 느슨하게 바꾸려면 재인증이 필요합니다.",
            },
        )
    store.risk_limits[rule_id] = payload.limit
    direction = "느슨하게" if new_limit > current.limit else "엄격하게"
    return ActionResult(
        ok=True,
        code="UPDATED",
        message=f"{current.name} 한도를 {direction} 변경했습니다. 즉시 적용됩니다.",
    )


# -------------------------------------------------------------------------- 연결


@router.get("/connections")
async def get_connections(store: StoreDep, state: StateQuery = None) -> ConnectionsPayload:
    resolved = _resolve(state)
    _guard(resolved)
    return fixtures.build_connections(store, resolved)


class TossTestRequest(BaseModel):
    scenario: str | None = None


@router.post("/connections/toss/test")
async def test_toss(payload: TossTestRequest, store: StoreDep) -> ConnectionTestResult:
    return fixtures.test_toss_connection(store, payload.scenario)


@router.post("/connections/accounts/{account_id}/stop")
async def stop_account(account_id: str, store: StoreDep) -> ActionResult:
    store.stopped_accounts.add(account_id)
    return ActionResult(
        ok=True,
        code="ACCOUNT_STOPPED",
        message=(
            "이 계좌의 신규 주문을 차단했습니다. 보유 포지션은 청산하지 않습니다."
        ),
    )


@router.post("/connections/accounts/{account_id}/resume")
async def resume_account(account_id: str, store: StoreDep) -> ActionResult:
    store.stopped_accounts.discard(account_id)
    return ActionResult(ok=True, code="ACCOUNT_RESUMED", message="계좌 주문을 재개했습니다.")


@router.post("/connections/mt5/{node_id}/resume")
async def resume_node(node_id: str, store: StoreDep) -> ActionResult:
    store.resumed_nodes.add(node_id)
    return ActionResult(
        ok=True,
        code="NODE_RESUMED",
        message="사용자 승인으로 이 노드의 자동매매를 재개했습니다.",
    )


# ---------------------------------------------------------------------- 감사 기록


@router.get("/audit")
async def get_audit(store: StoreDep, state: StateQuery = None) -> AuditPayload:
    resolved = _resolve(state)
    _guard(resolved)
    return fixtures.build_audit(store, resolved)


@router.get("/audit/{event_id}")
async def get_audit_event(event_id: str) -> AuditDetail:
    detail = fixtures.build_audit_detail(event_id)
    if detail is None:
        raise _not_found("감사 기록을 찾을 수 없습니다.")
    return detail


# ------------------------------------------------------------------------ 관리자


@router.get("/admin")
async def get_admin(store: StoreDep, state: StateQuery = None) -> AdminPayload:
    resolved = _resolve(state)
    _guard(resolved)
    return fixtures.build_admin(store, resolved)


# ------------------------------------------------------------------- 전체 제어


@router.get("/controls")
async def get_controls(store: StoreDep, state: StateQuery = None) -> ControlsPayload:
    return fixtures.build_controls(store, _resolve(state))


class ReauthRequest(BaseModel):
    reauthenticated: bool = False


@router.post("/controls/emergency-stop")
async def post_emergency_stop(payload: ReauthRequest, store: StoreDep) -> ActionResult:
    return fixtures.emergency_stop(store, payload.reauthenticated)


@router.post("/controls/resume")
async def post_resume(store: StoreDep) -> ActionResult:
    return fixtures.resume_all(store)


class LiquidateRequest(BaseModel):
    confirm_phrase: str
    reauthenticated: bool = False


@router.post("/controls/liquidate-all")
async def post_liquidate(payload: LiquidateRequest, store: StoreDep) -> ActionResult:
    return fixtures.liquidate_all(store, payload.confirm_phrase, payload.reauthenticated)


@router.post("/controls/reset")
async def post_reset(store: StoreDep) -> ActionResult:
    store.reset()
    return ActionResult(ok=True, code="RESET", message="콘솔 목업 상태를 초기화했습니다.")
