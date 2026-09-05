#  Distributed Rate Limiter & API Gateway

I built this project to deeply understand how large-scale systems protect themselves from traffic spikes and abuse. Instead of relying on third-party tools like AWS WAF, I implemented distributed rate-limiting algorithms from scratch.

This is a high-throughput API gateway protected by a Redis-backed distributed rate limiter, fully containerized with Docker, validated with rigorous load testing, and backed by a robust CI/CD pipeline.

## 🛠️ Tech Stack
- **Backend:** Python 3.12, FastAPI, Uvicorn
- **Distributed State:** Redis (with atomic Lua scripts to prevent race conditions)
- **Algorithms:** Token Bucket (burst-tolerant), Sliding Window Log (strict)
- **DevOps & Testing:** Docker, Docker Compose, GitHub Actions (CI/CD), Locust, Pytest

## 🏗️ Architecture & Flow
1. **Request Interception:** FastAPI middleware intercepts every incoming request and extracts the client IP (handling `X-Forwarded-For` proxies safely).
2. **Atomic State Check:** The middleware calls a Redis Lua script. This ensures the "check-and-consume" operation is 100% atomic, preventing race conditions even with thousands of concurrent requests across multiple server instances.
3. **Allow or Block:** If tokens/requests are available, the request proceeds and headers (`X-RateLimit-Remaining`) are added. If not, it instantly returns `HTTP 429 Too Many Requests` with a `Retry-After` header.

## 🐛 Challenges Faced & How I Solved Them
Building this wasn't just about writing algorithms; it was about making them production-ready:
- **TestClient `NoneType` Crashes:** During testing, FastAPI's `TestClient` sometimes leaves `request.client` as `None`, causing `AttributeError` crashes. I solved this by implementing defensive programming: a safe fallback chain (`X-Forwarded-For` → `request.client.host` → `"127.0.0.1"`) in both the middleware and endpoints.
- **CI/CD Redis Dependencies:** My tests passed locally but failed on GitHub Actions because there was no Redis server. I fixed this by adding a `services:` block to my GitHub Actions workflow, which provisions a healthy, ephemeral Redis container specifically for the test suite.
- **Floating-Point Precision in Tests:** Microsecond timing drift between `time.time()` calls caused flaky test failures (e.g., expecting `7.0` but getting `7.000004`). I resolved this by using `pytest.approx`, aligning with industry best practices for testing floating-point arithmetic.
- **Docker Build Context Bloat:** Initial Docker builds were failing with EOF errors because Docker was trying to copy my local `venv` folder. Adding a strict `.dockerignore` file reduced the build context from ~50MB to <1MB, fixing the issue instantly.

## 📈 Performance & Load Testing
Validated system resilience using **Locust**, simulating 100 concurrent users spawning at 10 users/sec for 30 seconds.

**Results:**
- **Throughput:** ~320 requests/second
- **Median Latency:** 3ms
- **99th Percentile Latency:** 12ms
- **Failure Rate:** 0.00% (HTTP 429 responses were gracefully handled by the rate limiter, preventing backend overload)

## 🚀 Quick Start (Docker)
You can spin up the API and Redis cache with one command:
```bash
docker-compose up -d --build
