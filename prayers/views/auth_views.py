from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.conf import settings
from drf_spectacular.utils import extend_schema

from prayers.serializers import (
    RegisterSerializer,
    UserProfileSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    EmailVerificationSerializer,
)
from prayers.models import EmailVerificationToken, PasswordResetToken
from prayers.services.auth_service import create_verification_token, consume_verification_token
from prayers.services.password_reset_service import request_password_reset, can_request_reset, consume_reset_token
from prayers.utils.email_service import EmailService
from apps.accounts.serializers import (
    RegisterResponseSerializer,
    VerifyEmailResponseSerializer,
    MessageResponseSerializer,
    ErrorResponseSerializer,
    LogoutResponseSerializer,
    GoogleAuthResponseSerializer,
)


class RegisterView(generics.CreateAPIView):
    """
    Register a new user.
    User is created and activated immediately.
    """
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Issue JWT tokens so user can log in immediately
        refresh = RefreshToken.for_user(user)
        
        return Response(
            RegisterResponseSerializer({
                'message': "Account created successfully.",
                'user': user,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Auth"])
class VerifyEmailView(generics.GenericAPIView):
    """
    Verify user's email address using the token from the email link.
    """
    serializer_class = EmailVerificationSerializer
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token_str = request.query_params.get('token')
        if not token_str:
            return Response(
                {"error": "Token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = EmailVerificationToken.objects.select_related('user').get(token=token_str)
        except EmailVerificationToken.DoesNotExist:
            return Response(
                {"error": "Invalid or expired verification token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not token.is_valid():
            return Response(
                ErrorResponseSerializer({'error': "Invalid or expired verification token."}).data,
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = token.user
        user.is_active = True
        user.save(update_fields=['is_active'])

        token.is_used = True
        token.save(update_fields=['is_used'])

        # Issue JWT tokens so user can log in immediately
        refresh = RefreshToken.for_user(user)
        return Response(
            VerifyEmailResponseSerializer({
                'message': "Email verified successfully. You can now log in.",
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Auth"])
class ResendVerificationEmailView(generics.GenericAPIView):
    """
    Resend the verification email (rate limited).
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        if not email:
            return Response(
                ErrorResponseSerializer({'error': "Email is required."}).data,
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Security: Don't reveal whether email exists
            return Response(
                MessageResponseSerializer({'message': "If the email exists and is unverified, a verification link has been sent."}).data,
                status=status.HTTP_200_OK,
            )

        if user.is_active:
            return Response(
                MessageResponseSerializer({'message': "This account is already verified."}).data,
                status=status.HTTP_200_OK,
            )

        # Rate limit: Check if a recent token was already created
        recent_token = EmailVerificationToken.objects.filter(
            user=user,
            created_at__gt=user.last_login or user.date_joined,
        ).exists()

        if recent_token:
            return Response(
                ErrorResponseSerializer({'error': "A verification email was already sent. Please wait before requesting again."}).data,
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        token = create_verification_token(user)
        EmailService.send_verification_email(user, token, request)

        return Response(
            MessageResponseSerializer({'message': "If the email exists and is unverified, a verification link has been sent."}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Auth"])
class PasswordResetRequestView(generics.GenericAPIView):
    """
    Request a password reset email.
    Rate limited to 1 per hour per email address.
    Does NOT reveal whether the email exists.
    """
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Security: Don't reveal whether email exists
            return Response(
                {"message": "If the email is registered, a reset link has been sent."},
                status=status.HTTP_200_OK,
            )

        # Rate limit check
        if not can_request_reset(user):
            return Response(
                {"error": "Too many reset requests. Please wait an hour before trying again."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        token = request_password_reset(user)
        EmailService.send_password_reset_email(user, token, request)

        return Response(
            {"message": "If the email is registered, a reset link has been sent."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(generics.GenericAPIView):
    """
    Confirm password reset using the token from email.
    Token is single-use and expires after 1 hour.
    All existing sessions are invalidated.
    """
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_str = serializer.validated_data['token']
        new_password = serializer.validated_data['password']

        user, error = consume_reset_token(token_str, new_password)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            MessageResponseSerializer({'message': "Password reset successful. Please log in with your new password."}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Auth"])
class ProfileView(generics.RetrieveUpdateAPIView):
    """Profile is only accessible to authenticated, email-verified users."""
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


@extend_schema(tags=["Auth"])
class DeleteAccountView(generics.DestroyAPIView):
    """Delete account — only for authenticated users."""
    permission_classes = [permissions.IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        user = request.user
        username = user.username
        user.delete()
        return Response(
            {'message': f'Account "{username}" has been permanently deleted.'},
            status=status.HTTP_204_NO_CONTENT,
        )


@extend_schema(tags=["Auth"])
class LogoutView(generics.GenericAPIView):
    """Logout and blacklist the refresh token."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {"error": "Invalid or expired refresh token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return Response(
                {"error": "Logout failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            LogoutResponseSerializer({'success': True}).data,
            status=status.HTTP_205_RESET_CONTENT,
        )


@extend_schema(tags=["Auth"])
class GoogleAuthView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token = request.data.get('id_token')
        if not token:
            return Response({'detail': 'id_token required'}, status=status.HTTP_400_BAD_REQUEST)

        client_id = settings.GOOGLE_CLIENT_ID

        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests
            idinfo = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                audience=client_id,
                clock_skew_in_seconds=10,
            )
        except ValueError as e:
            return Response({'detail': f'Invalid token: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'detail': f'Token verification failed: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        if not idinfo.get('email_verified'):
            return Response({'detail': 'Email not verified by Google'}, status=status.HTTP_400_BAD_REQUEST)

        email = idinfo['email'].lower()
        first_name = idinfo.get('given_name', '')
        last_name = idinfo.get('family_name', '')

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_active': True,
                },
            )

            if not created and not user.is_active:
                user.is_active = True
                user.save(update_fields=['is_active'])
        except Exception as e:
            return Response({'detail': f'User creation failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not created:
            updated = False
            if not user.first_name and first_name:
                user.first_name = first_name
                updated = True
            if not user.last_name and last_name:
                user.last_name = last_name
                updated = True
            if updated:
                user.save()

        try:
            refresh = RefreshToken.for_user(user)
        except Exception as e:
            return Response({'detail': f'Token generation failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            GoogleAuthResponseSerializer({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                },
            }).data,
            status=status.HTTP_200_OK,
        )