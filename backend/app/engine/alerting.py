"""
Strategy Pattern — Alert Routing Engine.

Different component failures require different alerting strategies.
The AlertDispatcher selects the correct strategy based on component_type + severity.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
import structlog
from app.db.postgres import get_db
from app.db.orm import AlertLogORM

log = structlog.get_logger(__name__)

# ── ANSI Colors for console output ────────────────────────────────────────────
_RED = "\033[91m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_BLUE = "\033[94m"
_RESET = "\033[0m"
_BOLD = "\033[1m"


# ── Abstract Strategy ─────────────────────────────────────────────────────────

class AlertStrategy(ABC):
    """Abstract alerting strategy. Each concrete strategy handles one priority level."""

    @abstractmethod
    async def alert(self, context: AlertContext) -> None: ...

    @property
    @abstractmethod
    def priority(self) -> str: ...


# ── Alert Context ─────────────────────────────────────────────────────────────

class AlertContext:
    def __init__(
        self,
        work_item_id: str,
        component_id: str,
        component_type: str,
        severity: str,
        message: str,
    ):
        self.work_item_id = work_item_id
        self.component_id = component_id
        self.component_type = component_type
        self.severity = severity
        self.message = message
        self.timestamp = datetime.utcnow().isoformat()


# ── Concrete Strategies ───────────────────────────────────────────────────────

class P0CriticalAlert(AlertStrategy):
    """
    P0 — CRITICAL: RDBMS, MCP Host failures.
    In production: PagerDuty page + Slack #incidents-p0 + SMS.
    Here: Full structured console output + webhook payload simulation.
    """

    @property
    def priority(self) -> str:
        return "P0"

    async def alert(self, ctx: AlertContext) -> None:
        print(
            f"\n{_RED}{_BOLD}🚨🚨🚨 P0 CRITICAL ALERT 🚨🚨🚨{_RESET}\n"
            f"  Work Item : {ctx.work_item_id}\n"
            f"  Component : {ctx.component_id} ({ctx.component_type})\n"
            f"  Message   : {ctx.message}\n"
            f"  Time      : {ctx.timestamp}\n"
            f"  Action    : IMMEDIATE PAGE — On-call engineer notified via PagerDuty\n"
            f"{_RED}{'='*60}{_RESET}\n"
        )
        webhook_payload = {
            "priority": "P0",
            "work_item_id": ctx.work_item_id,
            "component": ctx.component_id,
            "message": ctx.message,
            "channel": "#incidents-p0",
            "action": "page_oncall",
            "timestamp": ctx.timestamp,
        }
        log.critical("alert.p0", **webhook_payload)
        await _log_alert_to_db(ctx, "P0", "CRITICAL_PAGE", "pagerduty+slack+sms", webhook_payload)


class P1HighAlert(AlertStrategy):
    """P1 — HIGH: API, Queue failures. Urgent Slack notification."""

    @property
    def priority(self) -> str:
        return "P1"

    async def alert(self, ctx: AlertContext) -> None:
        print(
            f"\n{_YELLOW}{_BOLD}⚠️  P1 HIGH ALERT{_RESET}\n"
            f"  Work Item : {ctx.work_item_id}\n"
            f"  Component : {ctx.component_id} ({ctx.component_type})\n"
            f"  Message   : {ctx.message}\n"
            f"  Action    : Slack #incidents-p1 + PagerDuty low-urgency\n"
        )
        await _log_alert_to_db(ctx, "P1", "URGENT_NOTIFICATION", "slack+pagerduty", {
            "channel": "#incidents-p1", "priority": "P1",
        })


class P2MediumAlert(AlertStrategy):
    """P2 — MEDIUM: Cache failures. Standard team notification."""

    @property
    def priority(self) -> str:
        return "P2"

    async def alert(self, ctx: AlertContext) -> None:
        print(
            f"\n{_CYAN}{_BOLD}🔔 P2 MEDIUM ALERT{_RESET}\n"
            f"  Work Item : {ctx.work_item_id}\n"
            f"  Component : {ctx.component_id} ({ctx.component_type})\n"
            f"  Action    : Slack #incidents-p2\n"
        )
        await _log_alert_to_db(ctx, "P2", "STANDARD_NOTIFICATION", "slack", {
            "channel": "#incidents-p2", "priority": "P2",
        })


class P3LowAlert(AlertStrategy):
    """P3 — LOW: Informational. Log only."""

    @property
    def priority(self) -> str:
        return "P3"

    async def alert(self, ctx: AlertContext) -> None:
        print(
            f"\n{_BLUE}ℹ️  P3 LOW — {ctx.component_id}: {ctx.message}{_RESET}"
        )
        await _log_alert_to_db(ctx, "P3", "LOG_ONLY", "console", {
            "priority": "P3",
        })


# ── Component → Strategy Mapping ─────────────────────────────────────────────

_COMPONENT_PRIORITY_MAP: dict[str, str] = {
    "RDBMS": "P0",
    "MCP_HOST": "P0",
    "ASYNC_QUEUE": "P1",
    "API": "P1",
    "LOAD_BALANCER": "P1",
    "MICROSERVICE": "P1",
    "NOSQL": "P2",
    "CACHE": "P2",
}

_SEVERITY_OVERRIDE: dict[str, str] = {
    "P0": "P0",
    "P1": "P1",
    "P2": "P2",
    "P3": "P3",
}

_STRATEGY_MAP: dict[str, AlertStrategy] = {
    "P0": P0CriticalAlert(),
    "P1": P1HighAlert(),
    "P2": P2MediumAlert(),
    "P3": P3LowAlert(),
}


# ── Dispatcher ────────────────────────────────────────────────────────────────

class AlertDispatcher:
    """
    Selects and invokes the correct AlertStrategy based on component_type and severity.
    Strategy can be overridden per-component or per-severity — fully configurable.
    """

    def get_strategy(self, component_type: str, severity: str) -> AlertStrategy:
        # Severity override takes precedence if explicitly P0
        if severity in ("P0", "P1"):
            return _STRATEGY_MAP[severity]
        # Otherwise use component type mapping
        priority = _COMPONENT_PRIORITY_MAP.get(component_type.upper(), "P3")
        return _STRATEGY_MAP[priority]

    async def dispatch(
        self,
        component_type: str,
        severity: str,
        work_item_id: str,
        component_id: str,
        message: str,
    ) -> None:
        strategy = self.get_strategy(component_type, severity)
        ctx = AlertContext(
            work_item_id=work_item_id,
            component_id=component_id,
            component_type=component_type,
            severity=severity,
            message=message,
        )
        try:
            await strategy.alert(ctx)
        except Exception as exc:
            log.error("alert.dispatch.failed", error=str(exc), work_item=work_item_id)


# ── DB Helper ─────────────────────────────────────────────────────────────────

async def _log_alert_to_db(ctx: AlertContext, priority: str, alert_type: str, channel: str, payload: dict) -> None:
    try:
        async with get_db() as session:
            alert = AlertLogORM(
                work_item_id=ctx.work_item_id,
                priority=priority,
                alert_type=alert_type,
                channel=channel,
                payload=payload,
            )
            session.add(alert)
            await session.commit()
    except Exception as exc:
        log.error("alert.db_log.failed", error=str(exc))
