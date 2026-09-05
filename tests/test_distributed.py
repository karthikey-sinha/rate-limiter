"""Integration tests for distributed rate limiters (requires Redis)."""
import os
import time
import pytest
import redis

os.environ["TESTING"] = "True"

from app.algorithms.distributed_token_bucket import DistributedTokenBucket
from app.algorithms.distributed_sliding_window import DistributedSlidingWindow


def get_test_redis():
    """Get Redis client for testing."""
    client = redis.Redis(host="localhost", port=6379, db=1, decode_responses=True)
    try:
        client.ping()
        return client
    except redis.ConnectionError:
        pytest.skip("Redis not available, skipping distributed tests")


@pytest.fixture(autouse=True)
def clean_redis():
    """Clean test database before and after each test."""
    client = get_test_redis()
    client.flushdb()
    yield
    client.flushdb()


# ============================================
# Distributed Token Bucket Tests
# ============================================

class TestDistributedTokenBucket:

    def test_allows_initial_burst(self):
        client = get_test_redis()
        bucket = DistributedTokenBucket(client, max_tokens=5, refill_rate=1)

        for _ in range(5):
            result = bucket.allow_request("user1")
            assert result["allowed"] is True

        result = bucket.allow_request("user1")
        assert result["allowed"] is False

    def test_returns_remaining_tokens(self):
        client = get_test_redis()
        bucket = DistributedTokenBucket(client, max_tokens=10, refill_rate=1)

        result = bucket.allow_request("user1")
        assert result["allowed"] is True
        assert result["remaining"] == 9

    def test_returns_retry_after_when_rejected(self):
        client = get_test_redis()
        bucket = DistributedTokenBucket(client, max_tokens=1, refill_rate=2)

        bucket.allow_request("user1")
        result = bucket.allow_request("user1")

        assert result["allowed"] is False
        assert result["retry_after"] > 0

    def test_isolates_different_keys(self):
        client = get_test_redis()
        bucket = DistributedTokenBucket(client, max_tokens=2, refill_rate=1)

        bucket.allow_request("user1")
        bucket.allow_request("user1")
        assert bucket.allow_request("user1")["allowed"] is False

        assert bucket.allow_request("user2")["allowed"] is True

    def test_refills_over_time(self):
        client = get_test_redis()
        bucket = DistributedTokenBucket(client, max_tokens=5, refill_rate=10)

        for _ in range(5):
            bucket.allow_request("user1")
        assert bucket.allow_request("user1")["allowed"] is False

        time.sleep(0.5)

        result = bucket.allow_request("user1")
        assert result["allowed"] is True

    def test_reset(self):
        client = get_test_redis()
        bucket = DistributedTokenBucket(client, max_tokens=2, refill_rate=1)

        bucket.allow_request("user1")
        bucket.allow_request("user1")
        assert bucket.allow_request("user1")["allowed"] is False

        bucket.reset("user1")
        assert bucket.allow_request("user1")["allowed"] is True


# ============================================
# Distributed Sliding Window Tests
# ============================================

class TestDistributedSlidingWindow:

    def test_allows_up_to_max_requests(self):
        client = get_test_redis()
        window = DistributedSlidingWindow(client, max_requests=5, window_seconds=60)

        for _ in range(5):
            result = window.allow_request("user1")
            assert result["allowed"] is True

        result = window.allow_request("user1")
        assert result["allowed"] is False

    def test_returns_remaining_count(self):
        client = get_test_redis()
        window = DistributedSlidingWindow(client, max_requests=10, window_seconds=60)

        result = window.allow_request("user1")
        assert result["allowed"] is True
        assert result["remaining"] == 9

    def test_returns_retry_after_when_rejected(self):
        client = get_test_redis()
        window = DistributedSlidingWindow(client, max_requests=1, window_seconds=10)

        window.allow_request("user1")
        result = window.allow_request("user1")

        assert result["allowed"] is False
        assert result["retry_after"] > 0

    def test_isolates_different_keys(self):
        client = get_test_redis()
        window = DistributedSlidingWindow(client, max_requests=2, window_seconds=60)

        window.allow_request("user1")
        window.allow_request("user1")
        assert window.allow_request("user1")["allowed"] is False

        assert window.allow_request("user2")["allowed"] is True

    def test_sliding_window_expiry(self):
        client = get_test_redis()
        window = DistributedSlidingWindow(client, max_requests=2, window_seconds=1)

        window.allow_request("user1")
        window.allow_request("user1")
        assert window.allow_request("user1")["allowed"] is False

        time.sleep(1.1)

        assert window.allow_request("user1")["allowed"] is True

    def test_reset(self):
        client = get_test_redis()
        window = DistributedSlidingWindow(client, max_requests=2, window_seconds=60)

        window.allow_request("user1")
        window.allow_request("user1")
        assert window.allow_request("user1")["allowed"] is False

        window.reset("user1")
        assert window.allow_request("user1")["allowed"] is True