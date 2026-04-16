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
        fields = ('manual_offsets', 'calculation_method', 'use_hanafi')


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
        Sprint 1: Returns recovery state for each missed prayer.
        Checks both the 24h window AND whether the user has available tokens.
        Only shows protection when both conditions are met.
        """
        from datetime import timedelta

        prayer_keys = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']
        recovery = {}

        try:
            streak = Streak.objects.get(user=obj.user)
        except Streak.DoesNotExist:
            streak = None

        for key in prayer_keys:
            status = getattr(obj, f'{key}_status')
            if status == 'missed':
                # Recovery window: 24 hours from the end of the prayer day (midnight)
                window_end = obj.date + timedelta(days=1)
                from django.utils import timezone
                within_window = timezone.now() < window_end

                # Check if user has available tokens and is within window
                can_recover = within_window
                if streak and streak.protector_tokens <= 0:
                    can_recover = False

                if can_recover:
                    recovery[key] = {
                        'is_protected': True,
                        'expires_at': window_end.isoformat(),
                        'requires_qada': True,
                    }
                else:
                    recovery[key] = {
                        'is_protected': False,
                        'expires_at': window_end.isoformat() if within_window else None,
                        'requires_qada': False,
                    }
            else:
                recovery[key] = {
                    'is_protected': False,
                    'expires_at': None,
                    'requires_qada': False,
                }

        return recovery


class StreakSerializer(serializers.ModelSerializer):
    """Serializes the streak info."""
    display_streak = serializers.SerializerMethodField()
    max_protector_tokens = serializers.ReadOnlyField()
    weekly_token_limit = serializers.SerializerMethodField()
    weekly_tokens_remaining = serializers.SerializerMethodField()
    anti_gaming_cooldown_hours = serializers.SerializerMethodField()

    class Meta:
        model = Streak
        fields = (
            'current_streak', 'longest_streak', 'last_completed_date', 'display_streak',
            'protector_tokens', 'max_protector_tokens', 'tokens_reset_date',
            'weekly_tokens_used', 'weekly_token_limit', 'weekly_tokens_remaining',
            'last_token_used_at', 'anti_gaming_cooldown_hours',
        )
        read_only_fields = fields

    def get_display_streak(self, obj):
        """Returns the streak value to display (with grace period before noon)."""
        return obj.get_display_streak()

    def get_weekly_token_limit(self, obj):
        return obj.WEEKLY_TOKEN_LIMIT

    def get_weekly_tokens_remaining(self, obj):
        return max(0, obj.WEEKLY_TOKEN_LIMIT - obj.weekly_tokens_used)

    def get_anti_gaming_cooldown_hours(self, obj):
        return obj.ANTI_GAMING_COOLDOWN_HOURS
