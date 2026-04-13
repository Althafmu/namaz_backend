from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from prayers.serializers import CustomTokenObtainPairSerializer
from prayers.views import ProfileView, DeleteAccountView

# Custom login view that includes user data in the response
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

urlpatterns = [
    path('admin/', admin.site.urls),
    # JWT Authentication (custom view returns user info alongside tokens)
    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # User Profile
    path('api/auth/profile/', ProfileView.as_view(), name='user-profile'),
    # Delete Account
    path('api/auth/delete/', DeleteAccountView.as_view(), name='delete-account'),
    # Prayer API
    path('api/', include('prayers.urls')),
]
