class CIRISError(Exception):
    """Base exception for the SDK."""

class CIRISAPIError(CIRISError):
    """API errors with status codes"""
    def __init__(self, status_code: int, message: str):
        super().__init__(f"API Error {status_code}: {message}")
        self.status_code = status_code
        self.message = message

class CIRISTimeoutError(CIRISError):
    """Timeout errors"""

class CIRISConnectionError(CIRISError):
    """Connection errors - triggers retry"""
