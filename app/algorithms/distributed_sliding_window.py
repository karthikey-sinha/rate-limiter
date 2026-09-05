"""
Distributed Sliding Window Log using Redis Sorted Sets + Lua scripts.

Why Sorted Sets?
- Redis Sorted Sets store members with scores (timestamps)
- ZREMRANGEBYSCORE efficiently prunes old entries
- ZCARD counts entries in O(1) time
- Combined with Lua, the entire operation is atomic
"""
import time
import uuid
import redis


# Lua script for atomic sliding window check-and-record
SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local max_requests = tonumber(ARGV[1])
local window_seconds = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local request_id = ARGV[4]

local window_start = now - window_seconds

-- Remove expired entries
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- Count current requests in window
local current_count = redis.call('ZCARD', key)

if current_count < max_requests then
    -- Add new request with timestamp as score
    redis.call('ZADD', key, now, request_id)
    redis.call('EXPIRE', key, window_seconds + 1)
    local remaining = max_requests - current_count - 1
    return {1, remaining}  -- {allowed, remaining}
else
    -- Get oldest entry to calculate retry_after
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 0
    if #oldest > 0 then
        retry_after = math.ceil((tonumber(oldest[2]) + window_seconds) - now)
    end
    return {0, retry_after}  -- {rejected, retry_after_seconds}
end
"""


class DistributedSlidingWindow:
    """
    Redis-backed distributed Sliding Window Log rate limiter.
    Uses Sorted Sets for precise request counting across servers.
    """

    def __init__(self, redis_client: redis.Redis, max_requests: int, window_seconds: int):
        """
        Initialize distributed sliding window.

        Args:
            redis_client: Active Redis connection
            max_requests: Maximum requests allowed in window
            window_seconds: Window size in seconds
        """
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self.redis = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lua_sha = self.redis.script_load(SLIDING_WINDOW_LUA)

    def allow_request(self, key: str) -> dict:
        """
        Check if a request should be allowed (atomic operation).

        Args:
            key: Identifier (e.g., "ratelimit:ip:192.168.1.1")

        Returns:
            Dict with 'allowed' (bool), 'remaining' (int), 'retry_after' (float)
        """
        redis_key = f"ratelimit:sliding_window:{key}"
        now = time.time()
        request_id = f"{now}:{uuid.uuid4().hex[:8]}"

        result = self.redis.evalsha(
            self._lua_sha,
            1,
            redis_key,
            self.max_requests,
            self.window_seconds,
            now,
            request_id
        )

        allowed = bool(result[0])
        if allowed:
            return {
                "allowed": True,
                "remaining": int(result[1]),
                "retry_after": 0.0
            }
        else:
            return {
                "allowed": False,
                "remaining": 0,
                "retry_after": float(result[1])
            }

    def reset(self, key: str) -> None:
        """Reset a specific key's window."""
        redis_key = f"ratelimit:sliding_window:{key}"
        self.redis.delete(redis_key)