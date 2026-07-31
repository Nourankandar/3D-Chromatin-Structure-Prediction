"""
apps/accounts/services.py
Business logic for authentication, kept separate from the views/serializers
so it can be reused or unit tested independently of the HTTP layer.
"""

import logging
import random

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings

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

    @staticmethod
    def change_password(user: User, old_password: str, new_password: str) -> dict:
        """Change password after verifying the old one. No email involved."""
        if not user.check_password(old_password):
            return {"status": "error", "message": "Old password is incorrect."}

        user.set_password(new_password)
        user.save(update_fields=["password"])
        logger.info("Password changed successfully for user: %s", user.username)
        return {"status": "success", "message": "Password changed successfully."}
    
    
 # --- NEW METHODS ---

    @staticmethod
    def send_forgot_password_email(email: str) -> dict:
        user = User.objects.filter(email=email).first()
        if not user:
            return {"status": "error", "message": "User not found."}

        # Generate a 6-digit numeric code
        code = str(random.randint(100000, 999999))
        
        # Store in cache for 15 minutes (900 seconds)
        cache.set(f"reset_code_{email}", code, timeout=900)

        subject = "Password Reset Code"
        message = f"Hello {user.username},\n\nYour password reset code is: {code}\nThis code will expire in 15 minutes."

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            return {"status": "success", "message": "Password reset code sent to your email."}
        except Exception as e:
            logger.error(f"Failed to send email to {email}: {str(e)}")
            return {"status": "error", "message": "Failed to send email. Please check SMTP settings."}

    @staticmethod
    def reset_password_with_code(email: str, code: str, new_password: str) -> dict:
        cached_code = cache.get(f"reset_code_{email}")

        if not cached_code:
            return {"status": "error", "message": "Reset code has expired or does not exist."}

        if cached_code != code:
            return {"status": "error", "message": "Invalid reset code."}

        user = User.objects.filter(email=email).first()
        if not user:
            return {"status": "error", "message": "User not found."}

        # Set the new password
        user.set_password(new_password)
        user.save()
        
        # Invalidate the code immediately after successful use
        cache.delete(f"reset_code_{email}")

        return {"status": "success", "message": "Password has been reset successfully."}   