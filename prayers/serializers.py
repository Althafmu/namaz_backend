from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
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


class RegisterSerializer(serializers.ModelSerializer):
    """Handles user registration with secure password handling."""
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
    )
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'first_name', 'last_name')

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            is_active=True,  # Bypass email verification
        )
        Streak.objects.create(user=user)
        UserSettings.objects.create(user=user)
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    """Request password reset — rate limited, no email enumeration."""
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        # Security: Don't reveal whether email exists. Always return success.
        return value.lower().strip()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Reset password with time-limited token."""
    token = serializers.CharField(required=True)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
    )

    def validate_password(self, value):
        validate_password(value)
        return value


class EmailVerificationSerializer(serializers.Serializer):
    """Verify email with time-limited token."""
    token = serializers.CharField(required=True)


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
            'prayed_jumah',
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

from prayers.domain.constants import GroupRole, GroupPrivacy
from prayers.models import Group, GroupMembership


class GroupSerializer(serializers.ModelSerializer):
    """Serializer for Group model."""
    member_count = serializers.IntegerField(read_only=True)  # From annotation (Fix #6, #16)
    is_member = serializers.IntegerField(read_only=True)  # From annotation (Fix #16)
    user_role = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = (
            'id', 'name', 'description', 'privacy_level',
            'created_by', 'created_at', 'member_count',
            'is_member', 'user_role',
        )
        read_only_fields = ('id', 'created_by', 'created_at')
    
    def get_user_role(self, obj):
        """Read role from annotated value or compute if needed."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        if hasattr(obj, 'user_role') and obj.user_role:
            return obj.user_role
        try:
            membership = obj.memberships.get(
                user=request.user,
                status=MembershipStatus.ACTIVE,
            )
            return membership.role
        except GroupMembership.DoesNotExist:
            return None


class GroupMembershipSerializer(serializers.ModelSerializer):
    """Serializer for GroupMembership."""
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = GroupMembership
        fields = ('id', 'user', 'username', 'email', 'group', 'role', 'joined_at', 'status')
        read_only_fields = ('id', 'joined_at')
