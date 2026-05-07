from django.utils import timezone
from django.utils.crypto import get_random_string

from prayers.models.auth_tokens import EmailVerificationToken


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


def consume_verification_token(token_str):
    """
    Validate and consume a verification token.
    Returns (user, error_message) tuple.
    """
    try:
        token = EmailVerificationToken.objects.select_related('user').get(token=token_str)
    except EmailVerificationToken.DoesNotExist:
        return None, "Invalid or expired verification token."

    if not token.is_valid():
        token.is_used = True
        token.save(update_fields=['is_used'])
        return None, "Invalid or expired verification token."

    user = token.user
    token.is_used = True
    token.save(update_fields=['is_used'])

    return user, None
