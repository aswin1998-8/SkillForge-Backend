from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.responses import error_response, success_response
from apps.users.cookies import clear_jwt_cookies, set_jwt_cookies, tokens_for_user
from apps.users.serializers import (
    ForgotPasswordSerializer,
    GoogleAuthSerializer,
    InvitePreviewSerializer,
    LoginSerializer,
    ProfileSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)
from apps.users.services import (
    login_or_register_google,
    login_user,
    register_user,
    request_password_reset,
    resend_verification_email,
    reset_password,
    reset_user_progress,
    update_profile,
    verify_email_token,
)


class RegisterRateThrottle(AnonRateThrottle):
    scope = "register"


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class GoogleAuthRateThrottle(AnonRateThrottle):
    scope = "google"


class ResendVerificationRateThrottle(UserRateThrottle):
    scope = "resend_verification"


class ForgotPasswordRateThrottle(AnonRateThrottle):
    scope = "forgot_password"


class ResetPasswordRateThrottle(AnonRateThrottle):
    scope = "reset_password"


class InvitePreviewRateThrottle(AnonRateThrottle):
    scope = "invite_preview"


class InvitePreviewView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [InvitePreviewRateThrottle]

    def get(self, request: Request) -> Response:
        from apps.core.invites import preview_invite

        serializer = InvitePreviewSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        token_obj = preview_invite(serializer.validated_data["token"])
        return success_response(
            {
                "email": token_obj.email,
                "expires_at": token_obj.expires_at,
            }
        )


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [RegisterRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = register_user(**serializer.validated_data)
        refresh = tokens_for_user(user)
        response = success_response(
            UserSerializer(user).data,
            message="Registered",
            status=status.HTTP_201_CREATED,
        )
        return set_jwt_cookies(response, refresh)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = login_user(**serializer.validated_data)
        refresh = tokens_for_user(user)
        response = success_response(UserSerializer(user).data, message="Logged in")
        return set_jwt_cookies(response, refresh)


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [GoogleAuthRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = login_or_register_google(
            credential=serializer.validated_data["credential"],
            client_id=settings.GOOGLE_CLIENT_ID,
            invite_token=serializer.validated_data.get("invite_token") or "",
        )
        refresh = tokens_for_user(user)
        response = success_response(
            UserSerializer(user).data,
            message="Logged in with Google",
        )
        return set_jwt_cookies(response, refresh)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = verify_email_token(token=serializer.validated_data["token"])
        return success_response(
            UserSerializer(user).data,
            message="Email verified",
        )


class ResendVerificationView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ResendVerificationRateThrottle]

    def post(self, request: Request) -> Response:
        resend_verification_email(user=request.user)
        return success_response(message="Verification email sent")


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ForgotPasswordRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_password_reset(email=serializer.validated_data["email"])
        return success_response(
            message="If an account exists for that email, a reset link has been sent.",
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ResetPasswordRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = reset_password(
            token=serializer.validated_data["token"],
            password=serializer.validated_data["password"],
        )
        refresh = tokens_for_user(user)
        response = success_response(
            UserSerializer(user).data,
            message="Password updated",
        )
        return set_jwt_cookies(response, refresh)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        response = success_response(message="Logged out")
        return clear_jwt_cookies(response)


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        raw = request.COOKIES.get(settings.REFRESH_TOKEN_COOKIE_NAME)
        if not raw:
            return error_response(
                code="AUTH_REQUIRED",
                message="Refresh token missing.",
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            refresh = RefreshToken(raw)
        except (InvalidToken, TokenError):
            return error_response(
                code="AUTH_REQUIRED",
                message="Refresh token invalid.",
                status=status.HTTP_401_UNAUTHORIZED,
            )
        response = success_response(message="Token refreshed")
        return set_jwt_cookies(response, refresh)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return success_response(UserSerializer(request.user).data)


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.users.models import Profile

        profile, _ = Profile.objects.get_or_create(user=request.user)
        return success_response(ProfileSerializer(profile).data)

    def patch(self, request: Request) -> Response:
        serializer = ProfileSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile = update_profile(request.user, serializer.validated_data)
        return success_response(ProfileSerializer(profile).data)


class StaffResetProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        confirm = ""
        if isinstance(request.data, dict):
            confirm = str(request.data.get("confirm") or "")
        result = reset_user_progress(user=request.user, confirm=confirm)
        return success_response(result, message="Progress reset. Onboarding restarted.")

