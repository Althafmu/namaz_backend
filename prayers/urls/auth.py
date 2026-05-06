from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from prayers.views.auth_views import (
    DeleteAccountView,
    LogoutView,
    RegisterView,
    VerifyEmailView,
    ResendVerificationEmailView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    GoogleAuthView,
)
from core.authentication.views import CustomTokenObtainPairView

urlpatterns = [
    # JWT Authentication
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    # Registration & Email Verification
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', ResendVerificationEmailView.as_view(), name='resend-verification'),
    # Password Reset
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    # Delete Account
    path('delete/', DeleteAccountView.as_view(), name='delete-account'),
    # Google Sign-In
    path('google/', GoogleAuthView.as_view(), name='google-auth'),
]
