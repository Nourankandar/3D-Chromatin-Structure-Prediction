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
    @staticmethod
    def register_user(username: str, password: str, email: str = "", is_staff: bool = True) -> User:
        """Create a new staff/admin user account (inactive until email verified)."""
        if User.objects.filter(username=username).exists():
            raise ValueError("This username is already registered.")

        user = User.objects.create_user(username=username, password=password, email=email)
        user.is_staff = is_staff
        user.is_active = False   # <-- inactive until OTP verified
        user.save()

        logger.info("User registered (pending verification): %s", user.username)
        return user

    @staticmethod
    def send_signup_otp(user: User) -> dict:
        """Generate and email a signup verification code."""
        code = str(random.randint(100000, 999999))
        cache.set(f"signup_otp_{user.email}", code, timeout=900)  # 15 min

        subject = "Verify your account"
        message = f"Hello {user.username},\n\nYour verification code is: {code}\nThis code will expire in 15 minutes."

        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
            return {"status": "success", "message": "Verification code sent to your email."}
        except Exception as e:
            logger.error(f"Failed to send signup OTP to {user.email}: {str(e)}")
            return {"status": "error", "message": "Account created, but failed to send verification email."}

    @staticmethod
    def verify_signup_otp(email: str, code: str) -> dict:
        """Verify the signup code and activate the user."""
        cached_code = cache.get(f"signup_otp_{email}")

        if not cached_code:
            return {"status": "error", "message": "Verification code has expired or does not exist."}
        if cached_code != code:
            return {"status": "error", "message": "Invalid verification code."}

        user = User.objects.filter(email=email).first()
        if not user:
            return {"status": "error", "message": "User not found."}

        user.is_active = True
        user.save(update_fields=["is_active"])
        cache.delete(f"signup_otp_{email}")

        logger.info("User activated after OTP verification: %s", user.username)
        return {"status": "success", "message": "Account verified successfully. You can now log in."}

    @staticmethod
    def resend_signup_otp(email: str) -> dict:
        """Resend the signup verification code."""
        user = User.objects.filter(email=email).first()
        if not user:
            return {"status": "error", "message": "User not found."}
        if user.is_active:
            return {"status": "error", "message": "Account is already verified."}
        return AuthService.send_signup_otp(user)

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
        
        # نجيب المستخدم يدوياً أولاً عشان نقدر نميّز حالة "غير مفعّل"
        user_obj = User.objects.filter(username=username).first()

        if user_obj is None or not user_obj.check_password(password):
            return {
                "status": "unauthorized",
                "message": "Invalid username or password.",
            }

        if not user_obj.is_active:
            return {
                "status": "forbidden",
                "message": "Please verify your email before logging in.",
            }

        # الآن نستخدم authenticate() بشكل طبيعي (بيمرر لأنه is_active=True فعلاً)
        user = authenticate(request, username=username, password=password)
        if user is None:
            # حالة نادرة: مثلاً backend مخصص رفض تسجيل الدخول لسبب تاني
            return {
                "status": "unauthorized",
                "message": "Invalid username or password.",
            }

        if user.is_staff or user.is_superuser:
            tokens = AuthService.get_tokens_for_user(user)
            return {"status": "success", "tokens": tokens, "user": user}

        return {
            "status": "forbidden",
            "message": "This account does not have admin/staff privileges.",
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