"""
apps/accounts/services.py
Business logic for authentication, kept separate from the views/serializers
so it can be reused or unit tested independently of the HTTP layer.
"""

import logging

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger("apps.accounts")


class AuthService:
    @staticmethod
    def register_user(username: str, password: str, email: str = "", is_staff: bool = True) -> User:
        """Create a new staff/admin user account."""
        if User.objects.filter(username=username).exists():
            raise ValueError("This username is already registered.")

        user = User.objects.create_user(username=username, password=password, email=email)
        user.is_staff = is_staff
        user.save()

        logger.info("User registered successfully: %s", user.username)
        return user

    @staticmethod
    def get_tokens_for_user(user: User) -> dict:
        """Generate a fresh access/refresh token pair for a user."""
        refresh = RefreshToken.for_user(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

    @staticmethod
    def login_user(request, username: str, password: str) -> dict:
        """Authenticate credentials and return tokens for staff/superusers only."""
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_staff or user.is_superuser:
                tokens = AuthService.get_tokens_for_user(user)
                return {"status": "success", "tokens": tokens, "user": user}
            return {
                "status": "forbidden",
                "message": "This account does not have admin/staff privileges.",
            }
        return {
            "status": "unauthorized",
            "message": "Invalid username or password.",
        }

    @staticmethod
    def logout_user(refresh_token: str) -> None:
        """Blacklist the refresh token to invalidate the session."""
        token = RefreshToken(refresh_token)
        user_id = token.get("user_id", "Unknown")
        token.blacklist()
        logger.info("User ID %s logged out via token blacklisting.", user_id)
