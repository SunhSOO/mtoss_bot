import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from mtoss.api.app import create_app
from mtoss.api.console import fixtures
from mtoss.config import Settings

KEY = {"X-Internal-Key": "test-key"}

GET_PATHS = (
    "/console/v1/session",
    "/console/v1/dashboard",
    "/console/v1/strategies",
    "/console/v1/strategies/str-usdjpy-trend",
    "/console/v1/copy-sources",
    "/console/v1/copy-sources/cp-13f-brk",
    "/console/v1/approvals",
    "/console/v1/approvals/apv-13f-brkb",
    "/console/v1/orders",
    "/console/v1/orders/ord-0864",
    "/console/v1/risk-rules",
    "/console/v1/connections",
    "/console/v1/audit",
    "/console/v1/audit/aud-5521",
    "/console/v1/admin",
    "/console/v1/controls",
)


@pytest.fixture
def console_settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://mtoss:mtoss@127.0.0.1:1/mtoss",
        redis_url="redis://127.0.0.1:1/0",
        internal_api_key="test-key",
        console_stub_enabled=True,
    )


@pytest.fixture
def console(console_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(console_settings)) as test_client:
        test_client.post("/console/v1/controls/reset", headers=KEY)
        yield test_client


def test_stub_is_not_mounted_when_disabled(console_settings: Settings) -> None:
    disabled = Settings.model_validate(
        {**console_settings.model_dump(), "console_stub_enabled": False}
    )
    with TestClient(create_app(disabled)) as plain:
        assert plain.get("/console/v1/dashboard", headers=KEY).status_code == 404
        assert plain.get("/health/live").status_code == 200


def test_stub_requires_internal_key(console: TestClient) -> None:
    assert console.get("/console/v1/dashboard").status_code == 401


@pytest.mark.parametrize("path", GET_PATHS)
def test_get_paths_return_json_without_floats(console: TestClient, path: str) -> None:
    """A JSON float anywhere means a Decimal escaped as a double."""

    def reject(raw: str) -> float:
        raise AssertionError(f"console response contains a JSON float: {raw}")

    response = console.get(path, headers=KEY)
    assert response.status_code == 200, response.text
    json.loads(response.text, parse_float=reject)


@pytest.mark.parametrize("state", fixtures.STATES)
def test_dashboard_renders_every_simulated_state(console: TestClient, state: str) -> None:
    response = console.get(f"/console/v1/dashboard?state={state}", headers=KEY)
    if state == "forbidden":
        assert response.status_code == 403
    elif state == "server-error":
        assert response.status_code == 503
    else:
        assert response.status_code == 200, response.text


def test_money_is_serialised_as_plain_string(console: TestClient) -> None:
    payload = console.get("/console/v1/dashboard", headers=KEY).json()
    net_asset = payload["accounts"][0]["net_asset"]
    assert isinstance(net_asset, str)
    assert "E" not in net_asset and "e" not in net_asset


def test_unknown_order_offers_recheck_and_never_a_resubmit(console: TestClient) -> None:
    detail = console.get("/console/v1/orders/ord-0864", headers=KEY).json()
    assert detail["row"]["state"] == "UNKNOWN"
    assert detail["can_recheck_broker"] is True
    assert console.post("/console/v1/orders/ord-0864/resubmit", headers=KEY).status_code == 404
    assert console.post("/console/v1/orders/ord-0864/reorder", headers=KEY).status_code == 404
    recheck = console.post("/console/v1/orders/ord-0864/recheck-broker", headers=KEY)
    assert recheck.status_code == 200
    assert recheck.json()["code"] == "RECHECKED"


def test_settled_order_cannot_be_rechecked(console: TestClient) -> None:
    response = console.post("/console/v1/orders/ord-0852/recheck-broker", headers=KEY)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "RECHECK_NOT_APPLICABLE"


def test_approval_requires_a_recheck_before_approval(console: TestClient) -> None:
    response = console.post(
        "/console/v1/approvals/apv-13f-brkb/decide",
        headers=KEY,
        json={"action": "APPROVE"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "RECHECK_REQUIRED"


def test_approval_recheck_reports_changed_conditions(console: TestClient) -> None:
    recheck = console.post("/console/v1/approvals/apv-13f-brkb/recheck", headers=KEY).json()
    assert recheck["changed"] is True
    assert recheck["before_price"] != recheck["after_price"]
    decision = console.post(
        "/console/v1/approvals/apv-13f-brkb/decide",
        headers=KEY,
        json={"action": "APPROVE"},
    ).json()
    assert decision["status"] == "APPROVED"


def test_rejecting_an_approval_never_creates_an_order(console: TestClient) -> None:
    console.post("/console/v1/approvals/apv-ext-msft/recheck", headers=KEY)
    decision = console.post(
        "/console/v1/approvals/apv-ext-msft/decide",
        headers=KEY,
        json={"action": "REJECT"},
    ).json()
    assert decision["status"] == "REJECTED"
    assert decision["order_id"] is None


def test_loosening_a_risk_limit_requires_reauthentication(console: TestClient) -> None:
    response = console.patch(
        "/console/v1/risk-rules/risk-order-notional",
        headers=KEY,
        json={"limit": "20000000"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "REAUTH_REQUIRED"


def test_tightening_a_risk_limit_applies_immediately(console: TestClient) -> None:
    response = console.patch(
        "/console/v1/risk-rules/risk-order-notional",
        headers=KEY,
        json={"limit": "8000000"},
    )
    assert response.status_code == 200
    rules = console.get("/console/v1/risk-rules", headers=KEY).json()["rules"]
    updated = next(rule for rule in rules if rule["rule_id"] == "risk-order-notional")
    assert updated["limit"] == "8000000"


def test_emergency_stop_requires_reauthentication(console: TestClient) -> None:
    blocked = console.post(
        "/console/v1/controls/emergency-stop", headers=KEY, json={"reauthenticated": False}
    ).json()
    assert blocked["ok"] is False
    assert blocked["code"] == "REAUTH_REQUIRED"
    allowed = console.post(
        "/console/v1/controls/emergency-stop", headers=KEY, json={"reauthenticated": True}
    ).json()
    assert allowed["ok"] is True
    session = console.get("/console/v1/session", headers=KEY).json()
    assert session["emergency_stop"] is True


def test_liquidation_needs_the_phrase_and_reauthentication(console: TestClient) -> None:
    wrong = console.post(
        "/console/v1/controls/liquidate-all",
        headers=KEY,
        json={"confirm_phrase": "청산", "reauthenticated": True},
    ).json()
    assert wrong["code"] == "CONFIRM_PHRASE_MISMATCH"
    no_reauth = console.post(
        "/console/v1/controls/liquidate-all",
        headers=KEY,
        json={"confirm_phrase": fixtures.CONFIRM_PHRASE, "reauthenticated": False},
    ).json()
    assert no_reauth["code"] == "REAUTH_REQUIRED"
    ok = console.post(
        "/console/v1/controls/liquidate-all",
        headers=KEY,
        json={"confirm_phrase": fixtures.CONFIRM_PHRASE, "reauthenticated": True},
    ).json()
    assert ok["ok"] is True


def test_emergency_stop_does_not_liquidate_positions(console: TestClient) -> None:
    console.post(
        "/console/v1/controls/emergency-stop", headers=KEY, json={"reauthenticated": True}
    )
    controls = console.get("/console/v1/controls", headers=KEY).json()
    assert controls["emergency_stop"] is True
    assert controls["liquidation_running"] is False
    positions = console.get("/console/v1/orders", headers=KEY).json()["positions"]
    assert len(positions) > 0


def test_offline_node_stops_trading_and_never_auto_resumes(console: TestClient) -> None:
    offline = console.get("/console/v1/connections?state=mt5-offline", headers=KEY).json()
    node = offline["mt5_nodes"][0]
    assert node["status"]["label"] == "연결 끊김"
    assert node["auto_trading"] == "STOPPED_BY_OFFLINE"
    console.post("/console/v1/connections/mt5/node-seoul-01/resume", headers=KEY)
    resumed = console.get("/console/v1/connections?state=mt5-offline", headers=KEY).json()
    assert resumed["mt5_nodes"][0]["auto_trading"] == "RUNNING"


def test_toss_connection_test_distinguishes_failures(console: TestClient) -> None:
    for scenario, code in (
        ("auth", "AUTH"),
        ("no-account", "NO-ACCOUNT"),
        ("terms", "TERMS"),
        ("rate-limit", "RATE-LIMIT"),
    ):
        result = console.post(
            "/console/v1/connections/toss/test", headers=KEY, json={"scenario": scenario}
        ).json()
        assert result["passed"] is False
        assert result["code"] == code
    passing = console.post(
        "/console/v1/connections/toss/test", headers=KEY, json={"scenario": None}
    ).json()
    assert passing["passed"] is True


def test_approvals_are_sorted_by_expiry(console: TestClient) -> None:
    rows = console.get("/console/v1/approvals", headers=KEY).json()
    expiries = [row["expires_in_seconds"] for row in rows]
    assert expiries == sorted(expiries)


def test_reset_restores_pristine_state(console: TestClient) -> None:
    console.post(
        "/console/v1/controls/emergency-stop", headers=KEY, json={"reauthenticated": True}
    )
    console.post("/console/v1/controls/reset", headers=KEY)
    assert console.get("/console/v1/session", headers=KEY).json()["emergency_stop"] is False
