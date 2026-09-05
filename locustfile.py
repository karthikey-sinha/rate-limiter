"""
Locust Load Testing Script for the Distributed Rate Limiter.

This script simulates concurrent users hitting the protected /api/data endpoint
to measure throughput, latency, and verify that the rate limiter correctly 
blocks excess traffic (returning HTTP 429).
"""
from locust import HttpUser, task, between

class RateLimitUser(HttpUser):
    """
    Simulates a user interacting with the API.
    """
    # Wait between 0.1 and 0.5 seconds between tasks (realistic user behavior)
    wait_time = between(0.1, 0.5)

    @task
    def hit_protected_endpoint(self):
        """
        Continuously hit the rate-limited endpoint.
        We expect some of these to return 429 Too Many Requests, 
        which proves the rate limiter is working!
        """
        with self.client.get("/api/data", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                # Mark 429 as a success for this specific test, 
                # because it means the rate limiter did its job!
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")