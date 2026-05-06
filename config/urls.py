from django.contrib import admin
from django.urls import path, include
from django.utils import timezone
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.throttling import AnonRateThrottle
from prayers.serializers import CustomTokenObtainPairSerializer
from prayers.models import LoginAttempt
from core.health import health_check

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
    path('api/v1/health/', health_check, name='health_check'),
    path('api/v1/auth/', include('prayers.urls.auth')),
    path('api/v1/', include('prayers.urls')),
    path('api/v1/sunnah/', include('sunnah.urls')),
]
