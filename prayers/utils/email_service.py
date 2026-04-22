import os
import logging
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class EmailService:
    """
    Handles email sending for verification and password reset.
    In development, emails are printed to console instead of sent.
    Set FAKE_EMAIL_ENABLED=False and configure SMTP in production.
    """
    FAKE_EMAIL_ENABLED = os.environ.get('FAKE_EMAIL_ENABLED', 'True').lower() == 'true'
    FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@falah.app')

    @classmethod
    def _fake_send(cls, subject, body, to_email, html_body=None):
        logger.info("=" * 60)
        logger.info(f"[FAKE EMAIL] To: {to_email}")
        logger.info(f"[FAKE EMAIL] Subject: {subject}")
        logger.info(f"[FAKE EMAIL] Body:\n{body}")
        logger.info("=" * 60)

    @classmethod
    def send_verification_email(cls, user, token, request):
        """
        Send email verification link to the user.
        """
        verify_url = f"{cls._get_base_url(request)}/api/auth/verify-email/?token={token}"
        context = {
            'user': user,
            'verify_url': verify_url,
            'token': token,
        }

        subject = "Verify your email - Falah Prayer Tracker"
        body = (
            f"Hello {user.first_name or user.username},\n\n"
            f"Please verify your email by clicking the link below:\n\n"
            f"{verify_url}\n\n"
            f"This link expires in 24 hours.\n\n"
            f"If you didn't create a Falah account, ignore this email.\n"
        )

        if cls.FAKE_EMAIL_ENABLED:
            cls._fake_send(subject, body, user.email)
            return True

        try:
            EmailMessage(
                subject=subject,
                body=body,
                from_email=cls.FROM_EMAIL,
                to=[user.email],
            ).send(fail_silently=False)
            return True
        except Exception as e:
            logger.error(f"[EmailService] Failed to send verification email: {e}")
            return False

    @classmethod
    def send_password_reset_email(cls, user, token, request):
        """
        Send password reset link to the user.
        """
        reset_url = f"{cls._get_base_url(request)}/api/auth/reset-password/?token={token}"
        context = {
            'user': user,
            'reset_url': reset_url,
            'token': token,
        }

        subject = "Reset your password - Falah Prayer Tracker"
        body = (
            f"Hello {user.first_name or user.username},\n\n"
            f"Click the link below to reset your password:\n\n"
            f"{reset_url}\n\n"
            f"This link expires in 1 hour and can only be used once.\n\n"
            f"If you didn't request a password reset, ignore this email.\n"
        )

        if cls.FAKE_EMAIL_ENABLED:
            cls._fake_send(subject, body, user.email)
            return True

        try:
            EmailMessage(
                subject=subject,
                body=body,
                from_email=cls.FROM_EMAIL,
                to=[user.email],
            ).send(fail_silently=False)
            return True
        except Exception as e:
            logger.error(f"[EmailService] Failed to send password reset email: {e}")
            return False

    @classmethod
    def _get_base_url(cls, request):
        """Get base URL from request or environment."""
        if request:
            scheme = 'https' if request.is_secure() else 'http'
            host = request.get_host()
            return f"{scheme}://{host}"
        return os.environ.get('APP_BASE_URL', 'http://localhost:8000')