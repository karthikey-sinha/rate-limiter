"""
FastAPI Middleware for Distributed Rate Limiting.

Intercepts all incoming requests, extracts the client IP, and checks
the distributed rate limiter. Returns 429 Too Many Requests if limit exceeded.
"""
import time
from fastapi import Request, status
from fastapi.responses import JSONResponse
from loguru import logger

from app.db.redis import get_redis_client
from app.algorithms.distributed_token_bucket import DistributedTokenBucket

# Initialize the distributed rate limiter (e.g., 10 requests per 10 seconds)
# In production, these values would be loaded from environment variables/config
redis_client = get_redis_client()
rate_limiter = DistributedTokenBucket(
    redis_client=redis_client,
    max_tokens=10,
    refill_rate=1.0  # 1 token per second
)

async def rate_limit_middleware(request: Request, call_next):
    """
    Middleware to enforce rate limiting based on client IP.
    """
    # 1. Safely extract client IP (handles TestClient 'None' and proxies)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client is not None:
        client_ip = request.client.host
    else:
        client_ip = "127.0.0.1"  # Safe fallback for TestClient or unknown sources
    
    # Create a unique key for this IP
    limiter_key = f"ip:{client_ip}"
    
    # 2. Check rate limit
    result = rate_limiter.allow_request(limiter_key)
    
    if not result["allowed"]:
        # 3. Rate limit exceeded: Log and return 429
        retry_after = result["retry_after"]
        logger.warning(
            f"RATE_LIMIT_EXCEEDED | ip={client_ip} | path={request.url.path} | retry_after={retry_after:.2f}s"
        )
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "Too many requests. Please slow down.",
                "retry_after": retry_after
            },
            headers={"Retry-After": str(int(retry_after) + 1)}
        )
    
    # 4. Request allowed: Process it and measure latency
    start_time = time.time()
    response = await call_next(request)
    latency_ms = (time.time() - start_time) * 1000
    
    # 5. Add rate limit headers to successful responses (Best Practice)
    response.headers["X-RateLimit-Remaining"] = str(result["remaining"])
    response.headers["X-RateLimit-Limit"] = str(rate_limiter.max_tokens)
    
    logger.info(
        f"REQUEST_ALLOWED | ip={client_ip} | path={request.url.path} | "
        f"status={response.status_code} | latency_ms={latency_ms:.2f}"
    )
    
    return response