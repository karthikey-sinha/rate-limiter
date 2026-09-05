"""Pydantic models for API request/response validation."""
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    """Standard error response for rate-limited requests."""
    detail: str
    retry_after: float