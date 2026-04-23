from django.contrib import admin
from django.urls import path, include
from django.utils import timezone
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.throttling import AnonRateThrottle
from prayers.serializers import CustomTokenObtainPairSerializer
from prayers.views.auth_views import (
    DeleteAccountView,
    LogoutView,
    RegisterView,
    VerifyEmailView,
    ResendVerificationEmailView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
)
from prayers.models import LoginAttempt


class LoginRateThrottle(AnonRateThrottle):
    rate = '5/minute'
    num_failures_limit = 5
    lockout_minutes = 15

    def allow_request(self, request, view):
        ident = self.get_ident(request)
        now = timezone.now()
        window_start = now - timezone.timedelta(minutes=self.lockout_minutes)

        recent_failures = LoginAttempt.objects.filter(
            ip_address=ident,
            attempted_at__gte=window_start,
        ).count()

        if recent_failures >= self.num_failures_limit:
            return False

        return True

    def wait(self):
        return self.lockout_minutes * 60

    def get_ident(self, request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        return response

urlpatterns = [
    path('admin/', admin.site.urls),
    # JWT Authentication
    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/logout/', LogoutView.as_view(), name='logout'),
    # Registration & Email Verification
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/auth/verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('api/auth/resend-verification/', ResendVerificationEmailView.as_view(), name='resend-verification'),
    # Password Reset
    path('api/auth/password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('api/auth/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    # Delete Account
    path('api/auth/delete/', DeleteAccountView.as_view(), name='delete-account'),
    # Prayer API
    path('api/', include('prayers.urls')),
    # Sunna API (Growth intent)
    path('api/v2/sunnah/', include('sunnah.urls')),
]
