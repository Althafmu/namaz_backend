from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

from prayers.services.status_service import is_completion_status_db


class UserSettings(models.Model):
    """Stores per-user calculation settings for cloud sync (EPIC 3)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='settings',
    )
    manual_offsets = models.JSONField(
        default=dict,
        help_text='Per-prayer minute offsets, e.g. {"Fajr": 1, "Isha": -5}',
    )
    calculation_method = models.CharField(
        max_length=20,
        default='MWL',
        help_text='Prayer calculation method name',
    )
    use_hanafi = models.BooleanField(
        default=False,
        help_text='Whether to use Hanafi madhab for Asr calculation',
    )
    intent_level = models.CharField(
        max_length=20,
        default='foundation',
        choices=[('foundation', 'Foundation'), ('strengthening', 'Strengthening'), ('growth', 'Growth')],
    )
    intent_explicitly_set = models.BooleanField(
        default=False,
        help_text='Whether the user explicitly chose an intent level in onboarding.',
    )
    pause_notifications_until = models.DateField(
        null=True,
        blank=True,
        help_text='If set to today, notifications are paused until end of day.',
    )
    sunnah_enabled = models.BooleanField(
        default=False,
        help_text='Whether optional Sunna tracking is enabled for this user.',
    )

    def __str__(self):
        return f'Settings for {self.user.username}'



class EmailVerificationToken(models.Model):
    """Time-limited token for email verification."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='email_verification_token',
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = get_random_string(64)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        super().save(*args, **kwargs)

    def is_valid(self):
        return (
            not self.is_used
            and not self.is_expired
            and self.user.is_active is False
        )

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @classmethod
    def create_for_user(cls, user):
        # Invalidate any existing unexpired tokens for this user
        cls.objects.filter(user=user, is_used=False, expires_at__gt=timezone.now()).update(is_used=True)
        instance = cls.objects.create(user=user)
        return instance.token


class PasswordResetToken(models.Model):
    """Time-limited, single-use token for password reset."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_token',
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    RATE_LIMIT_HOURS = 1  # Can only request a reset once per hour

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = get_random_string(64)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=1)
        super().save(*args, **kwargs)

    def is_valid(self):
        return (
            not self.is_used
            and not self.is_expired
        )

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @classmethod
    def create_for_user(cls, user):
        # Invalidate any existing unexpired tokens for this user
        cls.objects.filter(user=user, is_used=False, expires_at__gt=timezone.now()).update(is_used=True)
        instance = cls.objects.create(user=user)
        return instance.token

    @classmethod
    def can_user_request_reset(cls, user):
        """Check rate limiting — can this user request a new reset token?"""
        recent = cls.objects.filter(
            user=user,
            created_at__gt=timezone.now() - timezone.timedelta(hours=cls.RATE_LIMIT_HOURS),
        ).exists()
        return not recent


