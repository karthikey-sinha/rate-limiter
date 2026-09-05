"""Integration tests for the FastAPI Rate Limiting Middleware."""
import os
import time
import pytest
from fastapi.testclient import TestClient

# Set testing environment
os.environ["TESTING"] = "True"

from app.main import app
from app.db.redis import get_redis_client

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_redis():
    """Clean Redis before each test to ensure isolation."""
    redis_client = get_redis_client()
    redis_client.flushdb()
    yield
    redis_client.flushdb()


def test_root_endpoint_allowed():
    """Test that the health check endpoint works."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_rate_limit_enforcement():
    """Test that the middleware blocks requests after the limit is reached."""
    # The limiter is configured for 10 requests per 10 seconds (1/sec refill)
    
    # First 10 requests should succeed
    for i in range(10):
        response = client.get("/api/data")
        assert response.status_code == 200
        assert "X-RateLimit-Remaining" in response.headers
    
    # 11th request should be blocked
    response = client.get("/api/data")
    assert response.status_code == 429
    
    data = response.json()
    assert "Too many requests" in data["detail"]
    assert "retry_after" in data
    assert data["retry_after"] > 0
    
    # Verify the Retry-After header is present
    assert "Retry-After" in response.headers


def test_rate_limit_headers_on_success():
    """Test that successful responses include rate limit headers."""
    response = client.get("/api/data")
    
    assert response.status_code == 200
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Limit" in response.headers
    assert int(response.headers["X-RateLimit-Limit"]) == 10