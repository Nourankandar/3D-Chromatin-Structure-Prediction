import re
from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserProfile

def validate_strong_password(value):
    if not re.search(r'[A-Z]', value):
        raise serializers.ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r'[a-z]', value):
        raise serializers.ValidationError("Password must contain at least one lowercase letter.")
    if not re.search(r'[0-9]', value):
        raise serializers.ValidationError("Password must contain at least one number.")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_\+=/\[\]~`]', value):
        raise serializers.ValidationError("Password must contain at least one special symbol.")
    return value

# --- SIGNUP FLOW SERIALIZERS ---

class InitiateSignupSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

class VerifySignupOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

class CompleteSignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    profile_image = serializers.ImageField(required=False, allow_null=True) # حقل الصورة الاختياري

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already registered.")
        return value

    def validate_password(self, value):
        return validate_strong_password(value)



class ResendSignupOTPSerializer(serializers.Serializer):
    """Serializer for resending the signup OTP"""
    email = serializers.EmailField()

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already fully registered.")
        return value
    
    
# --- EXISTING SERIALIZERS ---

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

class UserSerializer(serializers.ModelSerializer):
    # جلب رابط الصورة من الـ Profile المرتبط
    profile_image = serializers.ImageField(source='profile.profile_image', read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "is_staff", "is_superuser", "date_joined", "profile_image"]
        read_only_fields = fields

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    
    def validate_new_password(self, value):
        return validate_strong_password(value)

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user is associated with this email address.")
        return value

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8) 

    def validate_new_password(self, value):
        return validate_strong_password(value)

class UpdateProfileImageSerializer(serializers.Serializer):
    profile_image = serializers.ImageField(required=True)