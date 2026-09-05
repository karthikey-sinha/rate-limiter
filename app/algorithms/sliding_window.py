"""
Sliding Window Log Rate Limiting Algorithm.

Concept:
- Maintains a log (list) of timestamps for each request
- Counts requests within the sliding window (e.g., last 60 seconds)
- If count exceeds limit, reject the request
- Old timestamps are automatically pruned

Use Case:
- Provides exact rate limiting (no burst allowance)
- More memory-intensive than Token Bucket
- Perfect for strict compliance requirements
"""
import time
from collections import defaultdict, deque
from typing import Dict, Deque, Optional


class SlidingWindowLog:
    """
    Sliding Window Log rate limiter.
    
    Example:
        limiter = SlidingWindowLog(max_requests=100, window_seconds=60)
        # Allows exactly 100 requests per 60-second window
    """
    
    def __init__(self, max_requests: int, window_seconds: int):
        """
        Initialize the Sliding Window Log.
        
        Args:
            max_requests: Maximum requests allowed in the window
            window_seconds: Size of the sliding window in seconds
        """
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
            
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_logs: Dict[str, Deque[float]] = defaultdict(deque)
    
    def _prune_old_requests(self, key: str, current_time: float) -> None:
        """
        Remove timestamps older than the sliding window.
        
        Args:
            key: Identifier for the rate limit subject
            current_time: Current timestamp
        """
        window_start = current_time - self.window_seconds
        log = self.request_logs[key]
        
        # Remove timestamps outside the window
        while log and log[0] <= window_start:
            log.popleft()
    
    def allow_request(self, key: str) -> bool:
        """
        Check if a request should be allowed.
        
        Args:
            key: Identifier for the rate limit subject (IP, user ID, etc.)
            
        Returns:
            True if request is allowed, False if rate limited
        """
        current_time = time.time()
        self._prune_old_requests(key, current_time)
        
        log = self.request_logs[key]
        
        if len(log) < self.max_requests:
            log.append(current_time)
            return True
        
        return False
    
    def get_request_count(self, key: str) -> int:
        """
        Get the current number of requests in the window.
        
        Args:
            key: Identifier for the rate limit subject
            
        Returns:
            Number of requests in the current window
        """
        current_time = time.time()
        self._prune_old_requests(key, current_time)
        return len(self.request_logs[key])
    
    def get_remaining_requests(self, key: str) -> int:
        """
        Get how many more requests are allowed in this window.
        
        Args:
            key: Identifier for the rate limit subject
            
        Returns:
            Number of remaining allowed requests
        """
        current_count = self.get_request_count(key)
        return max(0, self.max_requests - current_count)
    
    def get_retry_after(self, key: str) -> float:
        """
        Calculate seconds until the next request will be allowed.
        
        Args:
            key: Identifier for the rate limit subject
            
        Returns:
            Seconds until next request allowed (0 if allowed now)
        """
        current_time = time.time()
        self._prune_old_requests(key, current_time)
        
        log = self.request_logs[key]
        
        if len(log) < self.max_requests:
            return 0.0
        
        # The oldest request in the window determines when the next slot opens
        oldest_request = log[0]
        return (oldest_request + self.window_seconds) - current_time
    
    def reset(self, key: Optional[str] = None) -> None:
        """
        Reset request log(s).
        
        Args:
            key: Specific key to reset, or None to reset all
        """
        if key is None:
            self.request_logs.clear()
        elif key in self.request_logs:
            del self.request_logs[key]