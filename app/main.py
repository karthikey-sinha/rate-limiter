"""Main FastAPI application for the Distributed Rate Limiter."""
from fastapi import FastAPI, Request
from loguru import logger

from app.middleware.rate_limit import rate_limit_middleware

# Configure structured JSON logging
logger.remove()
logger.add(lambda msg: print(msg), format="{message}", serialize=True)

app = FastAPI(
    title="Distributed Rate Limiter API",
    version="1.0.0",
    description="A high-throughput API gateway protected by distributed rate limiting."
)

# Attach the middleware
app.middleware("http")(rate_limit_middleware)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "message": "Rate Limiter API is running"}


@app.get("/api/data")
async def get_data(request: Request):
    """
    A sample protected endpoint. 
    The middleware will automatically rate limit requests to this route.
    """
    # Safely extract client IP (handles TestClient 'None' and proxies)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client is not None:
        client_ip = request.client.host
    else:
        client_ip = "127.0.0.1"  # Safe fallback for TestClient or unknown sources

    return {
        "message": "Success! You have accessed the protected resource.",
        "client_ip": client_ip
    }