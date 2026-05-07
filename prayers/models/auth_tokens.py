from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string


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

    @classmethod
    def consume_token(cls, token_str, new_password):
        """
        Validate and consume a token to reset the password.
        Returns (user, error_message) tuple.
        """
        try:
            token = cls.objects.select_related('user').get(token=token_str)
        except cls.DoesNotExist:
            return None, "Invalid or expired reset token."

        if not token.is_valid():
            token.is_used = True
            token.save(update_fields=['is_used'])
            return None, "Invalid or expired reset token."

        user = token.user
        user.set_password(new_password)
        user.save(update_fields=['password'])

        token.is_used = True
        token.save(update_fields=['is_used'])

        # Invalidate all existing refresh tokens for this user (session kill)
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
        OutstandingToken.objects.filter(user=user).delete()

        return user, None


