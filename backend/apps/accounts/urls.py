from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import *

urlpatterns = [
    path("signup/", SignupAPIView.as_view(), name="api_signup"),
    path("login/", LoginAPIView.as_view(), name="api_login"),
    path("logout/", LogoutAPIView.as_view(), name="api_logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("MyAccountAPIView/", MyAccountAPIView.as_view(), name="api_me"),
    path("change-password/", ChangePasswordAPIView.as_view(), name="change_password"),
]

# GET  /api/auth/MyAccountAPIView/             -> returns the currently authenticated user
# POST /api/auth/signup/         -> register a new staff user
# POST /api/auth/login/          -> authenticate, returns access/refresh JWT pair
# POST /api/auth/logout/         -> blacklists the supplied refresh token
# POST /api/auth/token/refresh/  -> exchange a refresh token for a new access token
