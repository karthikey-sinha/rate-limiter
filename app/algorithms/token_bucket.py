"""
Token Bucket Rate Limiting Algorithm.

Concept:
- A bucket holds up to `max_tokens` tokens
- Tokens are added at `refill_rate` tokens per second
- Each request consumes 1 token
- If no tokens available, request is rejected (429 Too Many Requests)

Use Case:
- Allows short bursts of traffic (up to max_tokens)
- Maintains long-term average rate (refill_rate)
- Perfect for APIs that want to allow occasional spikes
"""
import time
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class BucketState:
    """Tracks the state of a single token bucket."""
    tokens: float
    last_refill: float


class TokenBucket:
    """
    Token Bucket rate limiter.
    
    Example:
        limiter = TokenBucket(max_tokens=10, refill_rate=2)
        # Allows 10 requests instantly, then 2 requests/second sustained
    """
    
    def __init__(self, max_tokens: int, refill_rate: float):
        """
        Initialize the Token Bucket.
        
        Args:
            max_tokens: Maximum tokens the bucket can hold (burst capacity)
            refill_rate: Tokens added per second (sustained rate)
        """
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be positive")
            
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.buckets: Dict[str, BucketState] = {}
    
    def _refill(self, key: str, current_time: float) -> None:
        """
        Refill tokens based on elapsed time since last refill.
        
        Args:
            key: Identifier for the bucket (e.g., IP address, API key)
            current_time: Current timestamp
        """
        if key not in self.buckets:
            # Initialize new bucket as full
            self.buckets[key] = BucketState(
                tokens=float(self.max_tokens),
                last_refill=current_time
            )
            return
        
        bucket = self.buckets[key]
        elapsed = current_time - bucket.last_refill
        tokens_to_add = elapsed * self.refill_rate
        
        # Add tokens, cap at max_tokens
        bucket.tokens = min(self.max_tokens, bucket.tokens + tokens_to_add)
        bucket.last_refill = current_time
    
    def allow_request(self, key: str, tokens_required: int = 1) -> bool:
        """
        Check if a request should be allowed.
        
        Args:
            key: Identifier for the rate limit subject (IP, user ID, etc.)
            tokens_required: Number of tokens this request costs (default: 1)
            
        Returns:
            True if request is allowed, False if rate limited
        """
        current_time = time.time()
        self._refill(key, current_time)
        
        bucket = self.buckets[key]
        
        if bucket.tokens >= tokens_required:
            bucket.tokens -= tokens_required
            return True
        
        return False
    
    def get_remaining_tokens(self, key: str) -> float:
        """
        Get the current number of tokens available for a key.
        
        Args:
            key: Identifier for the bucket
            
        Returns:
            Number of tokens currently available
        """
        if key not in self.buckets:
            return float(self.max_tokens)
        
        # Refill first to get accurate count
        self._refill(key, time.time())
        return self.buckets[key].tokens
    
    def get_retry_after(self, key: str) -> float:
        """
        Calculate seconds until at least 1 token is available.
        Useful for the `Retry-After` HTTP header.
        
        Args:
            key: Identifier for the bucket
            
        Returns:
            Seconds until next token is available
        """
        if key not in self.buckets:
            return 0.0
        
        bucket = self.buckets[key]
        if bucket.tokens >= 1.0:
            return 0.0
        
        # Time needed to get 1 token
        tokens_needed = 1.0 - bucket.tokens
        return tokens_needed / self.refill_rate
    
    def reset(self, key: Optional[str] = None) -> None:
        """
        Reset bucket(s) to full capacity.
        
        Args:
            key: Specific key to reset, or None to reset all
        """
        if key is None:
            self.buckets.clear()
        elif key in self.buckets:
            del self.buckets[key]