"""Shared API auth dependencies."""
from app.core.security import get_current_user, get_optional_user

__all__ = ["get_current_user", "get_optional_user"]
