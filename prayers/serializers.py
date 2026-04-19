from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import DailyPrayerLog, Streak, UserSettings


class UserSerializer(serializers.ModelSerializer):
    """Read-only serializer for user info (used in login response)."""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')
        read_only_fields = fields


class UserSettingsSerializer(serializers.ModelSerializer):
    """Serializer for user calculation settings (cloud sync)."""

    class Meta:
        model = UserSettings
        fields = (
            'manual_offsets',
            'calculation_method',
            'use_hanafi',
            'intent_level',
            'intent_explicitly_set',
            'pause_notifications_until',
            'sunnah_enabled',
        )


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
        # Create a streak record and default settings for the new user
        Streak.objects.create(user=user)
        UserSettings.objects.create(user=user)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile with embedded settings (GET /api/auth/profile/)."""
    settings = UserSettingsSerializer(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'settings')


class DailyPrayerLogSerializer(serializers.ModelSerializer):
    """Serializes the daily prayer log."""
    is_complete = serializers.ReadOnlyField()
    completed_count = serializers.ReadOnlyField()
    jamaat_count = serializers.ReadOnlyField()
    # Sprint 1: Recovery state per prayer (for temporary streak protection UX)
    recovery = serializers.SerializerMethodField()

    class Meta:
        model = DailyPrayerLog
        fields = (
            'id', 'date',
            'fajr', 'dhuhr', 'asr', 'maghrib', 'isha',
            'fajr_in_jamaat', 'dhuhr_in_jamaat', 'asr_in_jamaat',
            'maghrib_in_jamaat', 'isha_in_jamaat',
            'fajr_status', 'fajr_reason', 'dhuhr_status', 'dhuhr_reason',
            'asr_status', 'asr_reason', 'maghrib_status', 'maghrib_reason',
            'isha_status', 'isha_reason',
            'location', 'is_complete', 'completed_count', 'jamaat_count',
            'created_at', 'updated_at',
            'recovery',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_recovery(self, obj):
        """
        Returns pre-computed recovery dict attached by the view via attach_recovery_to_logs.
        Serializer is dumb — no business logic here.
        """
        return getattr(obj, 'recovery', None)


class StreakSerializer(serializers.ModelSerializer):
    """Serializes the streak info. Internal fields hidden from frontend."""
    display_streak = serializers.SerializerMethodField()

    class Meta:
        model = Streak
        fields = (
            'current_streak', 'longest_streak', 'last_completed_date', 'display_streak',
        )
        read_only_fields = fields

    def get_display_streak(self, obj):
        """Returns the streak value to display (with grace period before noon)."""
        return obj.get_display_streak()
