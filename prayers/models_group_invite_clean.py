from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from prayers.domain.constants import GroupRole


class GroupInviteToken(models.Model):
    """Time-limited invite token (hashed for security)."""
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='invite_tokens',
    )
    token_hash = models.CharField(max_length=64, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_invites',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_revoked = models.BooleanField(default=False)
    max_uses = models.PositiveIntegerField(default=1)
    uses_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        indexes = [
            models.Index(fields=['token_hash']),
            models.Index(fields=['group', 'is_revoked']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)
    
    def is_valid(self):
        return (
            not self.is_revoked
            and timezone.now() < self.expires_at
            and self.uses_count < self.max_uses
        )
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
