"""Unit tests for MTTR calculation."""
import pytest
from datetime import datetime, timedelta
from app.engine.mttr import calculate_mttr_minutes, format_mttr


def test_mttr_basic():
    start = datetime(2024, 1, 1, 10, 0, 0)
    end = datetime(2024, 1, 1, 11, 30, 0)
    assert calculate_mttr_minutes(start, end) == 90.0


def test_mttr_less_than_one_minute():
    start = datetime(2024, 1, 1, 10, 0, 0)
    end = datetime(2024, 1, 1, 10, 0, 45)
    assert calculate_mttr_minutes(start, end) == 0.75


def test_mttr_invalid_order():
    start = datetime(2024, 1, 1, 11, 0, 0)
    end = datetime(2024, 1, 1, 10, 0, 0)
    with pytest.raises(ValueError, match="incident_end must be after"):
        calculate_mttr_minutes(start, end)


def test_mttr_same_time():
    now = datetime(2024, 1, 1, 10, 0, 0)
    with pytest.raises(ValueError):
        calculate_mttr_minutes(now, now)


def test_format_mttr_seconds():
    assert format_mttr(0.5) == "30s"


def test_format_mttr_minutes():
    assert "45m" in format_mttr(45.0)


def test_format_mttr_hours():
    result = format_mttr(125.0)
    assert "2h" in result
    assert "5m" in result


def test_mttr_24_hours():
    start = datetime(2024, 1, 1, 0, 0, 0)
    end = datetime(2024, 1, 2, 0, 0, 0)
    assert calculate_mttr_minutes(start, end) == 1440.0
