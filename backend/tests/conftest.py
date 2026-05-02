"""Pytest configuration and shared fixtures."""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta


@pytest.fixture
def sample_signal():
    return {
        "component_id": "CACHE_CLUSTER_01",
        "component_type": "CACHE",
        "severity": "P2",
        "message": "Connection timeout to Redis cluster",
        "error_code": "ERR_CONNECTION_TIMEOUT",
        "metadata": {"host": "redis-01.internal", "port": 6379},
        "timestamp": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def sample_rca_data():
    now = datetime.utcnow()
    return {
        "incident_start": now - timedelta(hours=2),
        "incident_end": now,
        "root_cause_category": "Infrastructure",
        "root_cause_description": "Redis cluster ran out of memory due to missing eviction policy configuration causing OOM errors",
        "fix_applied": "Restarted Redis with maxmemory-policy allkeys-lru and increased instance size from 4GB to 8GB",
        "prevention_steps": "Add Redis memory monitoring alert at 80% capacity and automate eviction policy validation in CI/CD pipeline",
        "affected_services": ["api-gateway", "session-service"],
        "submitted_by": "john.doe@company.com",
    }
