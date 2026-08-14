from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView

from .views import *

urlpatterns = [
    # --- 3-STEP SIGNUP URLS ---
    path("signup/initiate/", InitiateSignupAPIView.as_view(), name="signup_initiate"),
    path("signup/verify/", VerifySignupOTPAPIView.as_view(), name="signup_verify"),
    path("signup/complete/", CompleteSignupAPIView.as_view(), name="signup_complete"),

    # --- PROFILE URLS ---
    path("profile/update-image/", UpdateProfileImageAPIView.as_view(), name="update_profile_image"),

    # --- EXISTING URLS ---
    path("login/", LoginAPIView.as_view(), name="api_login"),
    path("logout/", LogoutAPIView.as_view(), name="api_logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("MyAccountAPIView/", MyAccountAPIView.as_view(), name="api_me"),
    path("change-password/", ChangePasswordAPIView.as_view(), name="change_password"),
    
    path("forgot-password/", ForgotPasswordAPIView.as_view(), name="forgot_password"),
    path("reset-password/", ResetPasswordAPIView.as_view(), name="reset_password"),
]

# السماح لـ Django بعرض ملفات الـ Media في بيئة التطوير (Development)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)