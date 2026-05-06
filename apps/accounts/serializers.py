from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Extends JWT login to include user info in the response."""
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'is_active': self.user.is_active,
        }
        return data

class UserProfileSerializer(serializers.ModelSerializer):
    """Read-only serializer for user info."""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')
        read_only_fields = fields

class RegisterResponseSerializer(serializers.Serializer):
    """DTO for registration response."""
    message = serializers.CharField()
    user = UserProfileSerializer()
    access = serializers.CharField()
    refresh = serializers.CharField()

class VerifyEmailResponseSerializer(serializers.Serializer):
    """DTO for email verification response."""
    message = serializers.CharField()
    access = serializers.CharField()
    refresh = serializers.CharField()

class MessageResponseSerializer(serializers.Serializer):
    """Generic message response."""
    message = serializers.CharField()

class ErrorResponseSerializer(serializers.Serializer):
    """Generic error response."""
    error = serializers.CharField()

class LogoutResponseSerializer(serializers.Serializer):
    """DTO for logout response."""
    success = serializers.BooleanField()
    error = serializers.CharField(required=False, allow_null=True)

class GoogleAuthResponseSerializer(serializers.Serializer):
    """DTO for Google authentication response."""
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserProfileSerializer()
