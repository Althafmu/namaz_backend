from datetime import timedelta
from django.utils import timezone
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.throttling import AnonRateThrottle
from prayers.serializers import CustomTokenObtainPairSerializer
from apps.accounts.models import LoginAttempt

class LoginRateThrottle(AnonRateThrottle):
    rate: str = '5/minute'
    num_failures_limit: int = 5
    lockout_minutes: int = 15

    def allow_request(self, request, view) -> bool:
        ident = self.get_ident(request)
        now = timezone.now()
        window_start = now - timedelta(minutes=self.lockout_minutes)

        recent_failures = LoginAttempt.objects.filter(
            ip_address=ident,
            attempted_at__gte=window_start,
        ).count()

        if recent_failures >= self.num_failures_limit:
            return False

        return True

    def wait(self) -> int:
        return self.lockout_minutes * 60

    def get_ident(self, request) -> str:
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]
