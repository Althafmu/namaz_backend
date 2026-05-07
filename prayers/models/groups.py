from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

from prayers.domain.constants import GroupRole, GroupPrivacy


class Group(models.Model):
    """Group for collective prayer tracking."""
    PRIVACY_CHOICES = GroupPrivacy.choices()
    
    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True)
    privacy_level = models.CharField(
        max_length=20,
        choices=PRIVACY_CHOICES,
        default=GroupPrivacy.PRIVATE,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_groups',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['privacy_level']),
        ]
    
    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    """Links users to groups with role-based access."""
    ROLE_CHOICES = GroupRole.choices()
    MEMBERSHIP_STATUS_CHOICES = [
        ('active', 'Active'),
        ('left', 'Left'),
        ('removed', 'Removed'),
        ('banned', 'Banned'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_memberships',
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=GroupRole.MEMBER,
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=MEMBERSHIP_STATUS_CHOICES,
        default='active',
    )
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'group'],
                name='unique_user_group_membership'
            )
        ]
        ordering = ['-joined_at']
        indexes = [
            models.Index(fields=['user', 'group']),
            models.Index(fields=['group', 'role']),
        ]
    
    def __str__(self):
        return f'{self.user.username} - {self.group.name} ({self.role})'
    
    @property
    def is_admin(self):
        return self.role == GroupRole.ADMIN
    
    @property
    def is_member(self):
        return self.role in [GroupRole.ADMIN, GroupRole.MEMBER]
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
