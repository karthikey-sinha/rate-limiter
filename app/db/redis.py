"""Redis connection manager for distributed rate limiting."""
import os
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

def get_redis_client() -> redis.Redis:
    """Get a Redis client instance."""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=0,
        decode_responses=True
    )