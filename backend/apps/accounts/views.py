from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser # جديد

from .serializers import *
from .services import AuthService

# --- SIGNUP VIEWS ---

class InitiateSignupAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = InitiateSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuthService.initiate_signup(email=serializer.validated_data["email"])
        if result["status"] == "success":
            return Response(result, status=status.HTTP_200_OK)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)


class VerifySignupOTPAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifySignupOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuthService.verify_signup_otp(
            email=serializer.validated_data["email"],
            code=serializer.validated_data["code"],
        )
        if result["status"] == "success":
            return Response(result, status=status.HTTP_200_OK)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)


class CompleteSignupAPIView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser] # ضروري لاستقبال الصور

    def post(self, request):
        serializer = CompleteSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuthService.complete_signup(
            email=serializer.validated_data["email"],
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
            profile_image=serializer.validated_data.get("profile_image"), # تمرير الصورة
            is_staff=True,
        )

        if result["status"] == "success":
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)


class ResendSignupOTPAPIView(APIView):
    """POST /api/auth/resend-signup-otp/ - resend verification code."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResendSignupOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuthService.resend_signup_otp(email=serializer.validated_data["email"])
        if result["status"] == "success":
            return Response(result, status=status.HTTP_200_OK)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)


# --- PROFILE VIEWS ---

class UpdateProfileImageAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = UpdateProfileImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuthService.update_profile_image(
            user=request.user,
            new_image=serializer.validated_data["profile_image"]
        )

        if result["status"] == "success":
            return Response(result, status=status.HTTP_200_OK)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)


class DeleteProfileImageAPIView(APIView):
    """DELETE /api/auth/profile/delete-image/ — Delete the current user's profile image."""
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        result = AuthService.delete_profile_image(user=request.user)

        if result["status"] == "success":
            return Response(result, status=status.HTTP_200_OK)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    

class LoginAPIView(APIView):
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
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            AuthService.logout_user(serializer.validated_data["refresh"])
        except Exception as exc:
            return Response({"status": "error", "message": f"Logout failed: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": "success", "message": "Logged out successfully, token revoked."}, status=status.HTTP_200_OK)


class MyAccountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)


class ChangePasswordAPIView(APIView):
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


class ForgotPasswordAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuthService.send_forgot_password_email(email=serializer.validated_data["email"])

        if result["status"] == "success":
            return Response(result, status=status.HTTP_200_OK)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuthService.reset_password_with_code(
            email=serializer.validated_data["email"],
            code=serializer.validated_data["code"],
            new_password=serializer.validated_data["new_password"],
        )

        if result["status"] == "success":
            return Response(result, status=status.HTTP_200_OK)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)