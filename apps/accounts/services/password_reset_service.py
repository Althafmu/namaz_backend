from django.db import transaction
from django.utils import timezone

from prayers.models.auth_tokens import PasswordResetToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from .result_contracts import AuthResult


@transaction.atomic
def request_password_reset(user):
    """
    Request a password reset for user.
    Invalidates existing unexpired tokens and creates a new one.
    Returns the token string.
    """
    # Invalidate any existing unexpired tokens for this user
    PasswordResetToken.objects.filter(
        user=user,
        is_used=False,
        expires_at__gt=timezone.now()
    ).update(is_used=True)

    instance = PasswordResetToken.objects.create(user=user)
    return instance.token


def can_request_reset(user):
    """
    Check rate limiting - can this user request a new reset token?
    Returns bool.
    """
    recent = PasswordResetToken.objects.filter(
        user=user,
        created_at__gt=timezone.now() - timezone.timedelta(hours=PasswordResetToken.RATE_LIMIT_HOURS),
    ).exists()
    return not recent


@transaction.atomic
def consume_reset_token(token_str, new_password):
    """
    Validate and consume a token to reset the password.
    Returns AuthResult.
    """
    try:
        token = PasswordResetToken.objects.select_related('user').get(token=token_str)
    except PasswordResetToken.DoesNotExist:
        return AuthResult.error_result("Invalid or expired reset token.")

    if not token.is_valid():
        token.is_used = True
        token.save(update_fields=['is_used'])
        return AuthResult.error_result("Invalid or expired reset token.")

    user = token.user
    user.set_password(new_password)
    user.save(update_fields=['password'])

    token.is_used = True
    token.save(update_fields=['is_used'])

    # Blacklist all outstanding tokens (session kill)
    outstanding_tokens = OutstandingToken.objects.filter(user=user)
    for outstanding_token in outstanding_tokens:
        BlacklistedToken.objects.get_or_create(token=outstanding_token)

    return AuthResult.success_result(user)
