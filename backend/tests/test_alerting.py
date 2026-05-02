"""Unit tests for the Alert Strategy Pattern."""
import pytest
from unittest.mock import AsyncMock, patch
from app.engine.alerting import (
    AlertDispatcher,
    AlertContext,
    P0CriticalAlert,
    P1HighAlert,
    P2MediumAlert,
    P3LowAlert,
)


def make_context(component_type="CACHE", severity="P2") -> AlertContext:
    return AlertContext(
        work_item_id="test-wi-001",
        component_id="TEST_COMPONENT",
        component_type=component_type,
        severity=severity,
        message="Test failure",
    )


@pytest.fixture
def dispatcher():
    return AlertDispatcher()


# ── Strategy Selection ────────────────────────────────────────────────────────

def test_rdbms_maps_to_p0(dispatcher):
    strategy = dispatcher.get_strategy("RDBMS", "P2")
    assert isinstance(strategy, P0CriticalAlert)


def test_mcp_host_maps_to_p0(dispatcher):
    strategy = dispatcher.get_strategy("MCP_HOST", "P2")
    assert isinstance(strategy, P0CriticalAlert)


def test_api_maps_to_p1(dispatcher):
    strategy = dispatcher.get_strategy("API", "P2")
    assert isinstance(strategy, P1HighAlert)


def test_async_queue_maps_to_p1(dispatcher):
    strategy = dispatcher.get_strategy("ASYNC_QUEUE", "P2")
    assert isinstance(strategy, P1HighAlert)


def test_cache_maps_to_p2(dispatcher):
    strategy = dispatcher.get_strategy("CACHE", "P2")
    assert isinstance(strategy, P2MediumAlert)


def test_nosql_maps_to_p2(dispatcher):
    strategy = dispatcher.get_strategy("NOSQL", "P2")
    assert isinstance(strategy, P2MediumAlert)


def test_unknown_component_maps_to_p3(dispatcher):
    strategy = dispatcher.get_strategy("UNKNOWN_COMPONENT", "P3")
    assert isinstance(strategy, P3LowAlert)


def test_severity_p0_overrides_component_type(dispatcher):
    """Explicit P0 severity overrides component-based mapping."""
    strategy = dispatcher.get_strategy("CACHE", "P0")
    assert isinstance(strategy, P0CriticalAlert)


def test_severity_p1_overrides_component_type(dispatcher):
    strategy = dispatcher.get_strategy("CACHE", "P1")
    assert isinstance(strategy, P1HighAlert)


# ── Strategy Priority Names ───────────────────────────────────────────────────

def test_strategy_priorities():
    assert P0CriticalAlert().priority == "P0"
    assert P1HighAlert().priority == "P1"
    assert P2MediumAlert().priority == "P2"
    assert P3LowAlert().priority == "P3"


# ── Dispatch Integration ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_does_not_raise(dispatcher):
    """Dispatch should not raise even if DB logging fails."""
    with patch("app.engine.alerting._log_alert_to_db", new_callable=AsyncMock) as mock_log:
        mock_log.side_effect = Exception("DB down")
        # Should swallow the error
        await dispatcher.dispatch(
            component_type="RDBMS",
            severity="P0",
            work_item_id="test-001",
            component_id="DB_PRIMARY",
            message="Primary DB is unreachable",
        )
