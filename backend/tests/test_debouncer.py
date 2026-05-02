"""Unit tests for the debounce logic."""
import pytest
from app.models.signal import SignalPayload, ComponentType, Severity
from datetime import datetime


def test_signal_component_id_uppercased():
    """component_id should always be normalized to uppercase."""
    signal = SignalPayload(
        component_id="cache_cluster_01",
        component_type=ComponentType.CACHE,
        severity=Severity.P2,
        message="Connection timeout",
    )
    assert signal.component_id == "CACHE_CLUSTER_01"


def test_signal_already_uppercase():
    signal = SignalPayload(
        component_id="RDBMS_PRIMARY",
        component_type=ComponentType.RDBMS,
        severity=Severity.P0,
        message="Primary DB down",
    )
    assert signal.component_id == "RDBMS_PRIMARY"


def test_signal_timestamp_defaults_to_now():
    signal = SignalPayload(
        component_id="API_GATEWAY",
        component_type=ComponentType.API,
        severity=Severity.P1,
        message="Gateway timeout",
    )
    assert signal.timestamp is not None
    # Should be within 1 second of now
    diff = abs((datetime.utcnow() - signal.timestamp).total_seconds())
    assert diff < 1.0


def test_signal_metadata_defaults_empty():
    signal = SignalPayload(
        component_id="QUEUE_01",
        component_type=ComponentType.ASYNC_QUEUE,
        severity=Severity.P1,
        message="Queue depth exceeded",
    )
    assert signal.metadata == {}


def test_signal_message_max_length():
    """Message longer than 2000 chars should be rejected."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SignalPayload(
            component_id="CACHE_01",
            component_type=ComponentType.CACHE,
            severity=Severity.P2,
            message="x" * 2001,
        )


def test_all_component_types_valid():
    for ct in ComponentType:
        signal = SignalPayload(
            component_id=f"{ct.value}_01",
            component_type=ct,
            severity=Severity.P3,
            message="Test signal",
        )
        assert signal.component_type == ct


def test_all_severity_levels_valid():
    for sev in Severity:
        signal = SignalPayload(
            component_id="TEST_COMPONENT",
            component_type=ComponentType.API,
            severity=sev,
            message="Test signal",
        )
        assert signal.severity == sev
