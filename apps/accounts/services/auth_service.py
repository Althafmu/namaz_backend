from django.db import transaction
from django.utils import timezone

from prayers.models.auth_tokens import EmailVerificationToken
from .result_contracts import AuthResult


def create_verification_token(user):
    """
    Create a new email verification token for user.
    Invalidates any existing unexpired tokens.
    Returns the token string.
    """
    # Invalidate any existing unexpired tokens for this user
    EmailVerificationToken.objects.filter(
        user=user,
        is_used=False,
        expires_at__gt=timezone.now()
    ).update(is_used=True)

    instance = EmailVerificationToken.objects.create(user=user)
    return instance.token


@transaction.atomic
def consume_verification_token(token_str):
    """
    Validate and consume a verification token.
    Returns AuthResult.
    """
    try:
        token = EmailVerificationToken.objects.select_related('user').get(token=token_str)
    except EmailVerificationToken.DoesNotExist:
        return AuthResult.error_result("Invalid or expired verification token.")

    if not token.is_valid():
        token.is_used = True
        token.save(update_fields=['is_used'])
        return AuthResult.error_result("Invalid or expired verification token.")

    user = token.user
    token.is_used = True
    token.save(update_fields=['is_used'])

    return AuthResult.success_result(user)
