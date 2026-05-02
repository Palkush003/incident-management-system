"""Unit tests for RCA validation logic."""
import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError
from app.models.rca import RCACreate, RootCauseCategory


def make_valid_rca(**overrides) -> dict:
    now = datetime.utcnow()
    base = {
        "incident_start": now - timedelta(hours=1),
        "incident_end": now,
        "root_cause_category": "Infrastructure",
        "root_cause_description": "Redis OOM due to missing maxmemory policy configuration",
        "fix_applied": "Restarted Redis with correct eviction policy and allocated more memory",
        "prevention_steps": "Added monitoring and automated policy validation in deployment pipeline",
        "submitted_by": "ops-engineer@company.com",
    }
    base.update(overrides)
    return base


# ── Valid RCA ─────────────────────────────────────────────────────────────────

def test_valid_rca_passes():
    rca = RCACreate(**make_valid_rca())
    assert rca.submitted_by == "ops-engineer@company.com"
    assert rca.mttr_would_be_positive()


def test_all_root_cause_categories_valid():
    for category in RootCauseCategory:
        rca = RCACreate(**make_valid_rca(root_cause_category=category.value))
        assert rca.root_cause_category == category


# ── End Time Validation ───────────────────────────────────────────────────────

def test_rca_end_before_start_rejected():
    now = datetime.utcnow()
    with pytest.raises(ValidationError, match="incident_end must be after"):
        RCACreate(**make_valid_rca(
            incident_start=now,
            incident_end=now - timedelta(hours=1)
        ))


def test_rca_end_equals_start_rejected():
    now = datetime.utcnow()
    with pytest.raises(ValidationError):
        RCACreate(**make_valid_rca(incident_start=now, incident_end=now))


# ── Required Fields ────────────────────────────────────────────────────────────

def test_missing_root_cause_description_rejected():
    data = make_valid_rca()
    del data["root_cause_description"]
    with pytest.raises(ValidationError):
        RCACreate(**data)


def test_missing_fix_applied_rejected():
    data = make_valid_rca()
    del data["fix_applied"]
    with pytest.raises(ValidationError):
        RCACreate(**data)


def test_missing_prevention_steps_rejected():
    data = make_valid_rca()
    del data["prevention_steps"]
    with pytest.raises(ValidationError):
        RCACreate(**data)


def test_missing_submitted_by_rejected():
    data = make_valid_rca()
    del data["submitted_by"]
    with pytest.raises(ValidationError):
        RCACreate(**data)


# ── Minimum Length Validation ─────────────────────────────────────────────────

def test_short_root_cause_description_rejected():
    with pytest.raises(ValidationError):
        RCACreate(**make_valid_rca(root_cause_description="Too short"))


def test_short_fix_applied_rejected():
    with pytest.raises(ValidationError):
        RCACreate(**make_valid_rca(fix_applied="Short"))


def test_short_prevention_steps_rejected():
    with pytest.raises(ValidationError):
        RCACreate(**make_valid_rca(prevention_steps="Short"))


# ── Optional Fields ───────────────────────────────────────────────────────────

def test_affected_services_optional():
    data = make_valid_rca()
    data.pop("affected_services", None)
    rca = RCACreate(**data)
    assert rca.affected_services == []


def test_affected_services_populated():
    rca = RCACreate(**make_valid_rca(affected_services=["svc-a", "svc-b"]))
    assert len(rca.affected_services) == 2
