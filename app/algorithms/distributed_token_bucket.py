"""
Distributed Token Bucket using Redis + Lua scripts.

Why Lua?
- Redis executes Lua scripts atomically (no race conditions)
- The check-and-decrement happens in a single Redis operation
- Without Lua, concurrent requests could read stale token counts
"""
import time
from typing import Optional
import redis


# Lua script for atomic token bucket check-and-consume
# This runs entirely inside Redis, guaranteeing atomicity
TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

-- Get current bucket state
local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

-- Initialize bucket if it doesn't exist
if tokens == nil then
    tokens = max_tokens
    last_refill = now
end

-- Calculate token refill
local elapsed = now - last_refill
local new_tokens = math.min(max_tokens, tokens + (elapsed * refill_rate))

-- Check if we have enough tokens
if new_tokens >= requested then
    new_tokens = new_tokens - requested
    redis.call('HMSET', key, 'tokens', new_tokens, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(max_tokens / refill_rate) + 10)
    return {1, math.floor(new_tokens)}  -- {allowed, remaining}
else
    redis.call('HMSET', key, 'tokens', new_tokens, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(max_tokens / refill_rate) + 10)
    local retry_after = (requested - new_tokens) / refill_rate
    return {0, math.ceil(retry_after)}  -- {rejected, retry_after_seconds}
end
"""


class DistributedTokenBucket:
    """
    Redis-backed distributed Token Bucket rate limiter.
    Works across multiple server instances using atomic Lua scripts.
    """

    def __init__(self, redis_client: redis.Redis, max_tokens: int, refill_rate: float):
        """
        Initialize distributed token bucket.

        Args:
            redis_client: Active Redis connection
            max_tokens: Maximum tokens (burst capacity)
            refill_rate: Tokens added per second (sustained rate)
        """
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be positive")

        self.redis = redis_client
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self._lua_sha = self.redis.script_load(TOKEN_BUCKET_LUA)

    def allow_request(self, key: str, tokens_required: int = 1) -> dict:
        """
        Check if a request should be allowed (atomic operation).

        Args:
            key: Identifier (e.g., "ratelimit:ip:192.168.1.1")
            tokens_required: Tokens this request costs

        Returns:
            Dict with 'allowed' (bool), 'remaining' (int), 'retry_after' (float)
        """
        redis_key = f"ratelimit:token_bucket:{key}"
        now = time.time()

        result = self.redis.evalsha(
            self._lua_sha,
            1,
            redis_key,
            self.max_tokens,
            self.refill_rate,
            now,
            tokens_required
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
        """Reset a specific key's bucket."""
        redis_key = f"ratelimit:token_bucket:{key}"
        self.redis.delete(redis_key)