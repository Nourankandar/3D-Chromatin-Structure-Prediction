<<<<<<< HEAD
from django.shortcuts import render
import json
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def api_login_view(request):
    if request.method == 'POST':
        try:
            # قراءة البيانات القادمة من الفرونت إند (Axios)
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            
            # التحقق من الحساب في قاعدة بيانات دجانغو
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                if user.is_staff or user.is_superuser:  # شرط أساسي: يجب أن يكون آدمن/موظف معمل
                    login(request, user)
                    return JsonResponse({
                        "status": "success", 
                        "message": "أهلاً بك يا آدمن، تم تسجيل الدخول بنجاح!"
                    })
                else:
                    return JsonResponse({
                        "status": "error", 
                        "message": "عذراً، هذا الحساب لا يملك صلاحيات الآدمن."
                    }, status=403)
            else:
                return JsonResponse({
                    "status": "error", 
                    "message": "اسم المستخدم أو كلمة المرور غير صحيحة."
                }, status=401)
                
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
            
    return JsonResponse({"status": "error", "message": "الطريقة غير مسموحة"}, status=405)


@csrf_exempt
def api_logout_view(request):
    logout(request)
    return JsonResponse({"status": "success", "message": "تم تسجيل الخروج بنجاح."})
=======
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

from .serializers import LoginSerializer, LogoutSerializer, SignupSerializer, UserSerializer
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


class MeAPIView(APIView):
    """GET /api/auth/me/ — return the currently authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)
>>>>>>> 1e8459bade3a2f5bc26fb6c95ac9cd8e18aa2bb0
