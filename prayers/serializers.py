from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import DailyPrayerLog, Streak


class UserSerializer(serializers.ModelSerializer):
    """Read-only serializer for user info (used in login response)."""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')
        read_only_fields = fields


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Extends JWT login to include user info in the response."""
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data


class RegisterSerializer(serializers.ModelSerializer):
    """Handles user registration."""
    password = serializers.CharField(write_only=True, min_length=6)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'first_name', 'last_name')

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        # Create a streak record for the new user
        Streak.objects.create(user=user)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile (first_name, last_name)."""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')
        read_only_fields = ('id', 'username', 'email')


class DailyPrayerLogSerializer(serializers.ModelSerializer):
    """Serializes the daily prayer log."""
    is_complete = serializers.ReadOnlyField()
    completed_count = serializers.ReadOnlyField()
    jamaat_count = serializers.ReadOnlyField()

    class Meta:
        model = DailyPrayerLog
        fields = (
            'id', 'date',
            'fajr', 'dhuhr', 'asr', 'maghrib', 'isha',
            'fajr_in_jamaat', 'dhuhr_in_jamaat', 'asr_in_jamaat',
            'maghrib_in_jamaat', 'isha_in_jamaat',
            'location', 'is_complete', 'completed_count', 'jamaat_count',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class StreakSerializer(serializers.ModelSerializer):
    """Serializes the streak info."""

    class Meta:
        model = Streak
        fields = ('current_streak', 'longest_streak', 'last_completed_date')
        read_only_fields = fields
