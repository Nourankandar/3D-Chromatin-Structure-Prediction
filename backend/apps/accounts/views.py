"""
apps/accounts/views.py
REST endpoints for authentication: signup, login, logout, "who am I".

Token refresh is handled by SimpleJWT's built-in TokenRefreshView, wired
directly in urls.py, so it doesn't need a custom view here.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import *
from .services import AuthService


class SignupAPIView(APIView):
    """POST /api/auth/signup/ — create a new staff account."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            AuthService.register_user(
                username=serializer.validated_data["username"],
                password=serializer.validated_data["password"],
                email=serializer.validated_data.get("email", ""),
                is_staff=True,
            )
        except ValueError as exc:
            return Response({"status": "error", "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"status": "success", "message": "Account created successfully."},
            status=status.HTTP_201_CREATED,
        )


class LoginAPIView(APIView):
    """POST /api/auth/login/ — authenticate and receive JWT tokens."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuthService.login_user(
            request,
            serializer.validated_data["username"],
            serializer.validated_data["password"],
        )

        if result["status"] == "success":
            return Response(
                {
                    "status": "success",
                    "message": "Welcome back, login successful.",
                    "tokens": result["tokens"],
                    "user": UserSerializer(result["user"]).data,
                },
                status=status.HTTP_200_OK,
            )
        if result["status"] == "forbidden":
            return Response({"status": "error", "message": result["message"]}, status=status.HTTP_403_FORBIDDEN)

        return Response({"status": "error", "message": result["message"]}, status=status.HTTP_401_UNAUTHORIZED)


class LogoutAPIView(APIView):
    """POST /api/auth/logout/ — blacklist the refresh token."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            AuthService.logout_user(serializer.validated_data["refresh"])
        except Exception as exc:
            return Response(
                {"status": "error", "message": f"Logout failed: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"status": "success", "message": "Logged out successfully, token revoked."},
            status=status.HTTP_200_OK,
        )


class MyAccountAPIView(APIView):
    """GET /api/auth/MyAccountAPIView/ — return the currently authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)


class ChangePasswordAPIView(APIView):
    """POST /api/auth/change-password/ — change password using the old one."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuthService.change_password(
            request.user,
            serializer.validated_data["old_password"],
            serializer.validated_data["new_password"],
        )

        if result["status"] == "success":
            return Response(result, status=status.HTTP_200_OK)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)