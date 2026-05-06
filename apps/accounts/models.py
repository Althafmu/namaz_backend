from django.db import models

class LoginAttempt(models.Model):
    """Tracks failed login attempts for abuse detection and account lockout."""

    ip_address = models.GenericIPAddressField()
    username_email = models.CharField(max_length=254, blank=True)
    attempted_at = models.DateTimeField(auto_now_add=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['ip_address', 'attempted_at']),
            models.Index(fields=['username_email', 'attempted_at']),
        ]

    def __str__(self):
        return f'Attempt from {self.ip_address} for {self.username_email}'
