from django.urls import path
<<<<<<< HEAD
from .views import api_login_view, api_logout_view

urlpatterns = [
    path('login/', api_login_view, name='api_login'),
    path('logout/', api_logout_view, name='api_logout'),
]
=======
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginAPIView, LogoutAPIView, MeAPIView, SignupAPIView

urlpatterns = [
    path("signup/", SignupAPIView.as_view(), name="api_signup"),
    path("login/", LoginAPIView.as_view(), name="api_login"),
    path("logout/", LogoutAPIView.as_view(), name="api_logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", MeAPIView.as_view(), name="api_me"),
]

# GET  /api/auth/me/             -> returns the currently authenticated user
# POST /api/auth/signup/         -> register a new staff user
# POST /api/auth/login/          -> authenticate, returns access/refresh JWT pair
# POST /api/auth/logout/         -> blacklists the supplied refresh token
# POST /api/auth/token/refresh/  -> exchange a refresh token for a new access token
>>>>>>> 1e8459bade3a2f5bc26fb6c95ac9cd8e18aa2bb0
