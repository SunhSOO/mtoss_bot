"""In-process mutable state for the console stub API.

The stub has no database. Approvals, account stops, node resumes and the
emergency controls mutate this object so the screens actually change while the
process is running. It resets on restart or via POST /console/v1/controls/reset.
"""

from dataclasses import dataclass, field

from mtoss.domain.approvals import ApprovalStatus


@dataclass
class ConsoleStore:
    """Mutable console state. Deliberately not thread-safe beyond the GIL."""

    approval_decisions: dict[str, ApprovalStatus] = field(default_factory=dict)
    approval_reasons: dict[str, str] = field(default_factory=dict)
    approval_rechecked: set[str] = field(default_factory=set)
    stopped_accounts: set[str] = field(default_factory=set)
    resumed_nodes: set[str] = field(default_factory=set)
    paused_sources: set[str] = field(default_factory=set)
    paused_strategies: set[str] = field(default_factory=set)
    rechecked_orders: set[str] = field(default_factory=set)
    risk_limits: dict[str, str] = field(default_factory=dict)
    emergency_stop: bool = False
    emergency_stopped_at: str | None = None
    cancel_progress_done: int = 0
    liquidation_running: bool = False
    toss_test_attempts: int = 0

    def reset(self) -> None:
        self.approval_decisions.clear()
        self.approval_reasons.clear()
        self.approval_rechecked.clear()
        self.stopped_accounts.clear()
        self.resumed_nodes.clear()
        self.paused_sources.clear()
        self.paused_strategies.clear()
        self.rechecked_orders.clear()
        self.risk_limits.clear()
        self.emergency_stop = False
        self.emergency_stopped_at = None
        self.cancel_progress_done = 0
        self.liquidation_running = False
        self.toss_test_attempts = 0
