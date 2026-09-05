"""Unit tests for rate limiting algorithms."""
import time
import pytest
from app.algorithms.token_bucket import TokenBucket
from app.algorithms.sliding_window import SlidingWindowLog


# ============================================
# Token Bucket Tests
# ============================================

class TestTokenBucket:
    """Test suite for TokenBucket algorithm."""
    
    def test_initialization_valid(self):
        """Test valid initialization parameters."""
        bucket = TokenBucket(max_tokens=10, refill_rate=2)
        assert bucket.max_tokens == 10
        assert bucket.refill_rate == 2
    
    def test_initialization_invalid_max_tokens(self):
        """Test that invalid max_tokens raises ValueError."""
        with pytest.raises(ValueError):
            TokenBucket(max_tokens=0, refill_rate=2)
        with pytest.raises(ValueError):
            TokenBucket(max_tokens=-5, refill_rate=2)
    
    def test_initialization_invalid_refill_rate(self):
        """Test that invalid refill_rate raises ValueError."""
        with pytest.raises(ValueError):
            TokenBucket(max_tokens=10, refill_rate=0)
        with pytest.raises(ValueError):
            TokenBucket(max_tokens=10, refill_rate=-1)
    
    def test_allows_initial_burst(self):
        """Test that bucket allows burst up to max_tokens."""
        bucket = TokenBucket(max_tokens=5, refill_rate=1)
        
        # Should allow 5 requests in a burst
        for _ in range(5):
            assert bucket.allow_request("user1") is True
        
        # 6th request should be rejected
        assert bucket.allow_request("user1") is False
    
    def test_rejects_when_empty(self):
        """Test that bucket rejects when tokens exhausted."""
        bucket = TokenBucket(max_tokens=2, refill_rate=1)
        
        assert bucket.allow_request("user1") is True
        assert bucket.allow_request("user1") is True
        assert bucket.allow_request("user1") is False  # Empty
    
    def test_refills_over_time(self):
        """Test that tokens refill at the correct rate."""
        bucket = TokenBucket(max_tokens=10, refill_rate=10)  # 10 tokens/sec
        
        # Exhaust all tokens
        for _ in range(10):
            bucket.allow_request("user1")
        assert bucket.allow_request("user1") is False
        
        # Wait 0.5 seconds (should refill 5 tokens)
        time.sleep(0.5)
        
        # Should now allow 5 more requests
        allowed = sum(1 for _ in range(10) if bucket.allow_request("user1"))
        assert allowed == 5
    
    def test_caps_at_max_tokens(self):
        """Test that bucket doesn't exceed max_tokens."""
        bucket = TokenBucket(max_tokens=5, refill_rate=100)
        
        # Wait a long time (would generate way more than 5 tokens)
        time.sleep(0.1)
        
        # Should still only allow 5 requests (capped at max)
        allowed = sum(1 for _ in range(10) if bucket.allow_request("user1"))
        assert allowed == 5
    
    def test_isolates_different_keys(self):
        """Test that different keys have independent buckets."""
        bucket = TokenBucket(max_tokens=2, refill_rate=1)
        
        # Exhaust user1's bucket
        bucket.allow_request("user1")
        bucket.allow_request("user1")
        assert bucket.allow_request("user1") is False
        
        # user2 should still have full bucket
        assert bucket.allow_request("user2") is True
        assert bucket.allow_request("user2") is True
    
    def test_get_remaining_tokens(self):
        """Test getting remaining token count."""
        bucket = TokenBucket(max_tokens=10, refill_rate=1)
        
        # New key should have full tokens
        assert bucket.get_remaining_tokens("user1") == 10
        
        # After 3 requests, should have 7
        for _ in range(3):
            bucket.allow_request("user1")
        assert bucket.get_remaining_tokens("user1") == 7
    
    def test_get_retry_after_when_allowed(self):
        """Test retry_after returns 0 when tokens available."""
        bucket = TokenBucket(max_tokens=5, refill_rate=1)
        assert bucket.get_retry_after("user1") == 0.0
    
    def test_get_retry_after_when_rejected(self):
        """Test retry_after returns positive value when rejected."""
        bucket = TokenBucket(max_tokens=1, refill_rate=2)  # 2 tokens/sec
        
        bucket.allow_request("user1")  # Exhaust bucket
        assert bucket.allow_request("user1") is False
        
        retry_after = bucket.get_retry_after("user1")
        # Should need ~0.5 seconds for 1 token at 2/sec
        assert 0.4 < retry_after < 0.6
    
    def test_reset_specific_key(self):
        """Test resetting a specific key."""
        bucket = TokenBucket(max_tokens=5, refill_rate=1)
        
        bucket.allow_request("user1")
        bucket.allow_request("user1")
        
        bucket.reset("user1")
        
        # Should be back to full
        assert bucket.get_remaining_tokens("user1") == 5
    
    def test_reset_all_keys(self):
        """Test resetting all keys."""
        bucket = TokenBucket(max_tokens=5, refill_rate=1)
        
        bucket.allow_request("user1")
        bucket.allow_request("user2")
        
        bucket.reset()
        
        assert bucket.get_remaining_tokens("user1") == 5
        assert bucket.get_remaining_tokens("user2") == 5
    
    def test_multi_token_request(self):
        """Test requests that consume multiple tokens."""
        bucket = TokenBucket(max_tokens=10, refill_rate=1)
        
        # Request costing 5 tokens
        assert bucket.allow_request("user1", tokens_required=5) is True
        assert bucket.get_remaining_tokens("user1") == 5
        
        # Request costing 6 tokens should fail
        assert bucket.allow_request("user1", tokens_required=6) is False
        
        # Request costing 5 tokens should succeed
        assert bucket.allow_request("user1", tokens_required=5) is True


# ============================================
# Sliding Window Log Tests
# ============================================

class TestSlidingWindowLog:
    """Test suite for SlidingWindowLog algorithm."""
    
    def test_initialization_valid(self):
        """Test valid initialization parameters."""
        limiter = SlidingWindowLog(max_requests=100, window_seconds=60)
        assert limiter.max_requests == 100
        assert limiter.window_seconds == 60
    
    def test_initialization_invalid_max_requests(self):
        """Test that invalid max_requests raises ValueError."""
        with pytest.raises(ValueError):
            SlidingWindowLog(max_requests=0, window_seconds=60)
        with pytest.raises(ValueError):
            SlidingWindowLog(max_requests=-5, window_seconds=60)
    
    def test_initialization_invalid_window(self):
        """Test that invalid window_seconds raises ValueError."""
        with pytest.raises(ValueError):
            SlidingWindowLog(max_requests=100, window_seconds=0)
        with pytest.raises(ValueError):
            SlidingWindowLog(max_requests=100, window_seconds=-1)
    
    def test_allows_up_to_max_requests(self):
        """Test that limiter allows exactly max_requests."""
        limiter = SlidingWindowLog(max_requests=5, window_seconds=60)
        
        for _ in range(5):
            assert limiter.allow_request("user1") is True
        
        # 6th request should be rejected
        assert limiter.allow_request("user1") is False
    
    def test_rejects_after_limit(self):
        """Test that limiter rejects after limit reached."""
        limiter = SlidingWindowLog(max_requests=2, window_seconds=60)
        
        assert limiter.allow_request("user1") is True
        assert limiter.allow_request("user1") is True
        assert limiter.allow_request("user1") is False
    
    def test_sliding_window_behavior(self):
        """Test that old requests fall out of the window."""
        # Use a very short window for testing
        limiter = SlidingWindowLog(max_requests=2, window_seconds=1)
        
        # Make 2 requests
        assert limiter.allow_request("user1") is True
        assert limiter.allow_request("user1") is True
        assert limiter.allow_request("user1") is False
        
        # Wait for window to slide
        time.sleep(1.1)
        
        # Should now allow new requests
        assert limiter.allow_request("user1") is True
    
    def test_isolates_different_keys(self):
        """Test that different keys have independent limits."""
        limiter = SlidingWindowLog(max_requests=2, window_seconds=60)
        
        # Exhaust user1
        limiter.allow_request("user1")
        limiter.allow_request("user1")
        assert limiter.allow_request("user1") is False
        
        # user2 should still have full quota
        assert limiter.allow_request("user2") is True
        assert limiter.allow_request("user2") is True
    
    def test_get_request_count(self):
        """Test getting current request count."""
        limiter = SlidingWindowLog(max_requests=10, window_seconds=60)
        
        assert limiter.get_request_count("user1") == 0
        
        limiter.allow_request("user1")
        limiter.allow_request("user1")
        limiter.allow_request("user1")
        
        assert limiter.get_request_count("user1") == 3
    
    def test_get_remaining_requests(self):
        """Test getting remaining request quota."""
        limiter = SlidingWindowLog(max_requests=10, window_seconds=60)
        
        assert limiter.get_remaining_requests("user1") == 10
        
        for _ in range(3):
            limiter.allow_request("user1")
        
        assert limiter.get_remaining_requests("user1") == 7
    
    def test_get_remaining_requests_never_negative(self):
        """Test that remaining requests never goes negative."""
        limiter = SlidingWindowLog(max_requests=2, window_seconds=60)
        
        # Exhaust limit
        limiter.allow_request("user1")
        limiter.allow_request("user1")
        limiter.allow_request("user1")  # Rejected but still counted? No, rejected means not logged
        
        assert limiter.get_remaining_requests("user1") == 0
    
    def test_get_retry_after_when_allowed(self):
        """Test retry_after returns 0 when allowed."""
        limiter = SlidingWindowLog(max_requests=5, window_seconds=60)
        assert limiter.get_retry_after("user1") == 0.0
    
    def test_get_retry_after_when_rejected(self):
        """Test retry_after returns positive value when rejected."""
        limiter = SlidingWindowLog(max_requests=1, window_seconds=10)
        
        limiter.allow_request("user1")
        assert limiter.allow_request("user1") is False
        
        retry_after = limiter.get_retry_after("user1")
        # Should be close to 10 seconds (window size)
        assert 9 < retry_after <= 10
    
    def test_reset_specific_key(self):
        """Test resetting a specific key."""
        limiter = SlidingWindowLog(max_requests=5, window_seconds=60)
        
        for _ in range(3):
            limiter.allow_request("user1")
        
        limiter.reset("user1")
        
        assert limiter.get_request_count("user1") == 0
        assert limiter.get_remaining_requests("user1") == 5
    
    def test_reset_all_keys(self):
        """Test resetting all keys."""
        limiter = SlidingWindowLog(max_requests=5, window_seconds=60)
        
        limiter.allow_request("user1")
        limiter.allow_request("user2")
        
        limiter.reset()
        
        assert limiter.get_request_count("user1") == 0
        assert limiter.get_request_count("user2") == 0
    
    def test_prunes_old_requests(self):
        """Test that old requests are properly pruned."""
        limiter = SlidingWindowLog(max_requests=5, window_seconds=1)
        
        # Make requests
        for _ in range(5):
            limiter.allow_request("user1")
        
        # Wait for window to pass
        time.sleep(1.1)
        
        # Old requests should be pruned, count should be 0
        assert limiter.get_request_count("user1") == 0