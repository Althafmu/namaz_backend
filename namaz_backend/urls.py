from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.throttling import AnonRateThrottle
from prayers.serializers import CustomTokenObtainPairSerializer
from prayers.views.auth_views import DeleteAccountView, LogoutView

class LoginRateThrottle(AnonRateThrottle):
    rate = '5/minute'

# Custom login view that includes user data in the response
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]

urlpatterns = [
    path('admin/', admin.site.urls),
    # JWT Authentication (custom view returns user info alongside tokens)
    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/logout/', LogoutView.as_view(), name='logout'),
    # Delete Account
    path('api/auth/delete/', DeleteAccountView.as_view(), name='delete-account'),
    # Prayer API
    path('api/', include('prayers.urls')),
    # Sunna API (Growth intent)
    path('api/v2/sunnah/', include('sunnah.urls')),
]
