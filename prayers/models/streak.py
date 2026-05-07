from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


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



class Streak(models.Model):
    """Tracks continuous prayer streak for a user."""

    MAX_PROTECTOR_TOKENS = 3
    WEEKLY_TOKEN_LIMIT = 3  # Max 3 token recoveries per week (PRD Sprint 1)
    ANTI_GAMING_COOLDOWN_HOURS = 24  # Cannot recover more than 1 day per 24h

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='streak',
    )
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_completed_date = models.DateField(null=True, blank=True)
    last_recalculated_at = models.DateTimeField(null=True, blank=True)

    protector_tokens = models.PositiveIntegerField(default=MAX_PROTECTOR_TOKENS)
    tokens_reset_date = models.DateField(null=True, blank=True)

    # Sprint 1: Weekly token tracking + anti-gaming
    weekly_tokens_used = models.PositiveIntegerField(default=0)  # Tokens consumed this week
    last_token_used_at = models.DateTimeField(null=True, blank=True)  # Anti-gaming cooldown

    def __str__(self):
        return f'{self.user.username} - {self.current_streak} day streak'

    @property
    def max_protector_tokens(self):
        return self.MAX_PROTECTOR_TOKENS

    @staticmethod
    def _current_week_start(target_date):
        """Returns Sunday 0:00 for the week containing target_date."""
        # weekday() returns 0=Monday, 6=Sunday. Convert to Sunday-based week.
        days_since_sunday = (target_date.weekday() + 1) % 7
        return target_date - timedelta(days=days_since_sunday)

    def _is_new_week(self, last_reset_date):
        """Check if we need a fresh weekly window (Sunday 3 AM local)."""
        if last_reset_date is None:
            return True
        today = timezone.localdate()
        current_week_start = self._current_week_start(today)
        return current_week_start > last_reset_date

    def recalculate(self, force=False, changed_date=None):
        """
        Recalculate streak data.

        Fully excused days keep the current streak alive without incrementing it.
        Pending or incomplete days do not count and will eventually break the chain.
        Recovery (protection) window: if a missed day has active protection, the chain
        stays alive so the user can still log Qada before the window closes.
        """
        from prayers.services.streak_service import recalculate_streak
        recalculate_streak(self, force=force, changed_date=changed_date)

    def can_use_token(self, target_date=None):
        """
        Sprint 1: Check if user can consume a token right now.
        Returns dict with 'allowed' bool and 'reason' string.
        Anti-gaming: Cannot recover more than 1 day per 24h.
        """
        # Check weekly limit
        if self.weekly_tokens_used >= self.WEEKLY_TOKEN_LIMIT:
            return {
                'allowed': False,
                'reason': 'Weekly recovery limit reached. Tokens reset every Sunday.',
            }

        # Check anti-gaming cooldown
        if self.last_token_used_at:
            hours_since = (timezone.now() - self.last_token_used_at).total_seconds() / 3600
            if hours_since < self.ANTI_GAMING_COOLDOWN_HOURS:
                remaining = self.ANTI_GAMING_COOLDOWN_HOURS - hours_since
                return {
                    'allowed': False,
                    'reason': f'Cooldown active. Next recovery allowed in {int(remaining)} hours.',
                }

        return {'allowed': True, 'reason': None}

    def consume_protector_token(self):
        """
        Consume a protector token to save streak.
        Returns True if token was consumed, False if none available.
        Sprint 1: Now tracks weekly usage and last token used time for anti-gaming.
        """
        can_use = self.can_use_token()
        if not can_use['allowed']:
            return False

        if self.protector_tokens > 0:
            self.protector_tokens -= 1
            self.weekly_tokens_used += 1
            self.last_token_used_at = timezone.now()
            self.save(update_fields=['protector_tokens', 'weekly_tokens_used', 'last_token_used_at'])
            return True
        return False

    def restore_protector_token(self):
        """Restore a protector token (e.g., after Qada prayer)."""
        if self.protector_tokens < self.MAX_PROTECTOR_TOKENS:
            self.protector_tokens += 1
            self.save(update_fields=['protector_tokens'])

    def get_display_streak(self):
        """
        Returns the streak to display to the user.
        During the first 12 hours of the day, shows the previous streak for motivation.
        """
        now = timezone.localtime()
        today = now.date()

        if self.current_streak > 0 or now.hour >= 12 or not self.last_completed_date:
            return self.current_streak

        yesterday = today - timedelta(days=1)
        if self.last_completed_date != yesterday:
            return self.current_streak

        streak_count = 0
        previous_date = None
        logs = DailyPrayerLog.objects.filter(user=self.user, date__lte=yesterday).order_by('-date')
        for log in logs:
            if previous_date and (previous_date - log.date).days > 1:
                break
            if not log.is_valid_for_streak:
                break
            if log.counts_toward_streak_increment:
                streak_count += 1
            previous_date = log.date

        return streak_count


import hashlib
from django.utils.crypto import get_random_string
from prayers.domain.constants import GroupRole, GroupPrivacy


