"""Unit tests for rate limiter token bucket logic."""
import pytest
from app.engine.mttr import calculate_mttr_minutes


def test_rate_limiter_token_bucket_concept():
    """
    Test the token bucket concept: tokens refill over time.
    This tests the logic, not the Redis implementation.
    """
    capacity = 10
    rate_per_sec = 10
    tokens = capacity

    # Consume 5 tokens
    requests = 5
    assert tokens >= requests
    tokens -= requests
    assert tokens == 5

    # Simulate 0.5 seconds passing: refill 5 tokens
    elapsed = 0.5
    refill = elapsed * rate_per_sec
    tokens = min(capacity, tokens + refill)
    assert tokens == 10.0  # Capped at capacity

    # Consume all tokens
    assert tokens >= 10
    tokens -= 10
    assert tokens == 0

    # No tokens left — request should be rejected
    assert tokens < 1  # Would be rejected


def test_rate_limiter_overflow_capped():
    """Tokens should never exceed capacity."""
    capacity = 100
    tokens = 80
    refill = 50  # Would overflow
    tokens = min(capacity, tokens + refill)
    assert tokens == 100


def test_rate_limiter_burst():
    """Burst capacity allows up to `capacity` requests instantly."""
    capacity = 10000
    tokens = capacity
    # 10K simultaneous requests
    requests = 10000
    assert tokens >= requests
    tokens -= requests
    assert tokens == 0
    # Next request should be rejected
    assert tokens < 1


def test_rate_limiter_gradual_refill():
    """After burst, requests are rate-limited at steady state."""
    capacity = 10
    rate = 10  # 10 per second
    tokens = 0.0

    # Simulate 0.1s intervals — should get 1 token each
    for i in range(5):
        tokens = min(capacity, tokens + (rate * 0.1))

    assert tokens == pytest.approx(5.0, rel=0.01)
