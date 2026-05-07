from dataclasses import dataclass
from typing import Optional

from django.contrib.auth import get_user_model

User = get_user_model()


@dataclass
class AuthResult:
    """Typed result contract for auth operations."""
    success: bool
    user: Optional[User]
    error: Optional[str]
    token: Optional[str] = None

    @classmethod
    def success_result(cls, user: User, token: str = None) -> 'AuthResult':
        """Create a success result."""
        return cls(success=True, user=user, error=None, token=token)

    @classmethod
    def error_result(cls, error: str) -> 'AuthResult':
        """Create an error result."""
        return cls(success=False, user=None, error=error, token=None)
