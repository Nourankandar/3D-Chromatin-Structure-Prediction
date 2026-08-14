import logging
import random
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings
from .models import UserProfile

logger = logging.getLogger("apps.accounts")

class AuthService:
    
    # --- SIGNUP FLOW SERVICES ---

    @staticmethod
    def initiate_signup(email: str) -> dict:
        if User.objects.filter(email=email).exists():
            return {"status": "error", "message": "Email already registered."}

        code = str(random.randint(100000, 999999))
        cache.set(f"signup_otp_{email}", code, timeout=300) 

        subject = "Verify your account"
        message = f"Hello,\n\nYour verification code is: {code}\nThis code will expire in 5 minutes."

        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
            logger.info(f"Signup OTP sent to {email}")
            return {"status": "success", "message": "Verification code sent to your email."}
        except Exception as e:
            logger.error(f"Failed to send signup OTP to {email}: {str(e)}")
            return {"status": "error", "message": "Failed to send verification email. Check SMTP settings."}

    @staticmethod
    def verify_signup_otp(email: str, code: str) -> dict:
        cached_code = cache.get(f"signup_otp_{email}")

        if not cached_code:
            return {"status": "error", "message": "Verification code has expired or does not exist."}
        if cached_code != code:
            return {"status": "error", "message": "Invalid verification code."}

        cache.delete(f"signup_otp_{email}")
        cache.set(f"signup_verified_{email}", True, timeout=900)

        logger.info(f"Email {email} verified successfully for signup.")
        return {"status": "success", "message": "Email verified successfully. Proceed to complete registration."}

    @staticmethod
    def complete_signup(email: str, username: str, password: str, profile_image=None, is_staff: bool = True) -> dict:
        is_verified = cache.get(f"signup_verified_{email}")
        
        if not is_verified:
            return {"status": "error", "message": "Email not verified or session expired. Please restart signup."}

        if User.objects.filter(username=username).exists():
            return {"status": "error", "message": "This username is already registered."}

        user = User.objects.create_user(username=username, password=password, email=email)
        user.is_staff = is_staff
        user.is_active = True
        user.save()

        # إنشاء الملف الشخصي وحفظ الصورة إذا تم توفيرها
        UserProfile.objects.create(user=user, profile_image=profile_image)

        cache.delete(f"signup_verified_{email}")
        logger.info("User registered completely: %s", user.username)
        return {"status": "success", "message": "Account created successfully. You can now log in."}

    # --- PROFILE SERVICES ---

    @staticmethod
    def update_profile_image(user: User, new_image) -> dict:
        # البحث عن الـ Profile أو إنشائه في حال لم يكن موجوداً
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # مسح الصورة القديمة من السيرفر (اختياري، يفضل لتوفير المساحة)
        if profile.profile_image and not created:
            profile.profile_image.delete(save=False)
            
        profile.profile_image = new_image
        profile.save()
        return {"status": "success", "message": "Profile image updated successfully."}

    # --- EXISTING SERVICES ---
    # (الأكواد الخاصة بـ login_user, logout_user, change_password, forgot_password تبقى كما هي تماماً من الرد السابق)
    # ...


    @staticmethod
    def get_tokens_for_user(user: User) -> dict:
        refresh = RefreshToken.for_user(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

    @staticmethod
    def login_user(request, username: str, password: str) -> dict:
        user_obj = User.objects.filter(username=username).first()

        if user_obj is None or not user_obj.check_password(password):
            return {"status": "unauthorized", "message": "Invalid username or password."}

        if not user_obj.is_active:
            return {"status": "forbidden", "message": "Your account is disabled."}

        user = authenticate(request, username=username, password=password)
        if user is None:
            return {"status": "unauthorized", "message": "Invalid username or password."}

        if user.is_staff or user.is_superuser:
            tokens = AuthService.get_tokens_for_user(user)
            return {"status": "success", "tokens": tokens, "user": user}

        return {"status": "forbidden", "message": "This account does not have admin/staff privileges."}

    @staticmethod
    def logout_user(refresh_token: str) -> None:
        token = RefreshToken(refresh_token)
        user_id = token.get("user_id", "Unknown")
        token.blacklist()
        logger.info("User ID %s logged out via token blacklisting.", user_id)

    @staticmethod
    def change_password(user: User, old_password: str, new_password: str) -> dict:
        if not user.check_password(old_password):
            return {"status": "error", "message": "Old password is incorrect."}

        user.set_password(new_password)
        user.save(update_fields=["password"])
        logger.info("Password changed successfully for user: %s", user.username)
        return {"status": "success", "message": "Password changed successfully."}
    
    @staticmethod
    def send_forgot_password_email(email: str) -> dict:
        user = User.objects.filter(email=email).first()
        if not user:
            return {"status": "error", "message": "User not found."}

        code = str(random.randint(100000, 999999))
        cache.set(f"reset_code_{email}", code, timeout=900)

        subject = "Password Reset Code"
        message = f"Hello {user.username},\n\nYour password reset code is: {code}\nThis code will expire in 15 minutes."

        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
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

        user.set_password(new_password)
        user.save()
        cache.delete(f"reset_code_{email}")

        return {"status": "success", "message": "Password has been reset successfully."}