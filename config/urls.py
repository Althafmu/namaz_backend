from django.contrib import admin
from django.urls import path, include
from core.health import health_check

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/health/', health_check, name='health_check'),
    path('api/v1/auth/', include('prayers.urls.auth')),
    path('api/v1/', include('prayers.urls')),
    path('api/v1/sunnah/', include('sunnah.urls')),
]
