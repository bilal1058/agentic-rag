from core.config import check_rate_limit, rate_limit_remaining, reset_rate_limit, RedisRateLimiter


def test_in_memory_rate_limiter():
    session_id = "test_session_rl"
    reset_rate_limit(session_id)

    # First request must be allowed
    allowed, retry_after = check_rate_limit(session_id)
    assert allowed is True
    assert retry_after == 0.0

    rem = rate_limit_remaining(session_id)
    assert rem >= 0

    reset_rate_limit(session_id)


def test_redis_rate_limiter_class():
    limiter = RedisRateLimiter(window_seconds=10, max_requests=2)
    user_key = "user_123"

    allowed, wait = limiter.check(user_key)
    assert allowed is True

    allowed, wait = limiter.check(user_key)
    assert allowed is True

    # 3rd request must be blocked
    allowed, wait = limiter.check(user_key)
    assert allowed is False
    assert wait > 0
