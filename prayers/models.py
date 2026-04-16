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

    def __str__(self):
        return f'Settings for {self.user.username}'


class DailyPrayerLog(models.Model):
    """Tracks the 5 daily prayers for a user on a specific date."""

    LOCATION_CHOICES = [
        ('mosque', 'Mosque'),
        ('home', 'Home'),
        ('work', 'Work'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='prayer_logs',
    )
    date = models.DateField(default=timezone.localdate)

    # Each prayer: True = prayed, False = missed
    fajr = models.BooleanField(default=False)
    dhuhr = models.BooleanField(default=False)
    asr = models.BooleanField(default=False)
    maghrib = models.BooleanField(default=False)
    isha = models.BooleanField(default=False)

    # Optional metadata per log
    fajr_in_jamaat = models.BooleanField(default=False)
    dhuhr_in_jamaat = models.BooleanField(default=False)
    asr_in_jamaat = models.BooleanField(default=False)
    maghrib_in_jamaat = models.BooleanField(default=False)
    isha_in_jamaat = models.BooleanField(default=False)

    # Phase 2: Qada, Excused, and Pending states.
    STATUS_CHOICES = [
        ('on_time', 'On Time'),
        ('late', 'Late'),
        ('missed', 'Missed'),
        ('qada', 'Qada (Made Up)'),
        ('excused', 'Excused'),
        ('pending', 'Pending Evaluation'),
    ]
    fajr_status = models.CharField(max_length=20, default='pending', choices=STATUS_CHOICES)
    fajr_reason = models.CharField(max_length=255, blank=True, null=True)
    dhuhr_status = models.CharField(max_length=20, default='pending', choices=STATUS_CHOICES)
    dhuhr_reason = models.CharField(max_length=255, blank=True, null=True)
    asr_status = models.CharField(max_length=20, default='pending', choices=STATUS_CHOICES)
    asr_reason = models.CharField(max_length=255, blank=True, null=True)
    maghrib_status = models.CharField(max_length=20, default='pending', choices=STATUS_CHOICES)
    maghrib_reason = models.CharField(max_length=255, blank=True, null=True)
    isha_status = models.CharField(max_length=20, default='pending', choices=STATUS_CHOICES)
    isha_reason = models.CharField(max_length=255, blank=True, null=True)

    location = models.CharField(
        max_length=20,
        choices=LOCATION_CHOICES,
        default='home',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']

    def __str__(self):
        completed = sum([self.fajr, self.dhuhr, self.asr, self.maghrib, self.isha])
        return f'{self.user.username} - {self.date} - {completed}/5'

    @property
    def is_complete(self):
        """Returns True if all 5 prayers are logged."""
        return all([self.fajr, self.dhuhr, self.asr, self.maghrib, self.isha])

    @property
    def completed_count(self):
        return sum([self.fajr, self.dhuhr, self.asr, self.maghrib, self.isha])

    @property
    def jamaat_count(self):
        return sum([
            self.fajr_in_jamaat,
            self.dhuhr_in_jamaat,
            self.asr_in_jamaat,
            self.maghrib_in_jamaat,
            self.isha_in_jamaat,
        ])

    @property
    def prayer_statuses(self):
        return [
            self.fajr_status,
            self.dhuhr_status,
            self.asr_status,
            self.maghrib_status,
            self.isha_status,
        ]

    @property
    def prayer_completed(self):
        return [
            self.fajr,
            self.dhuhr,
            self.asr,
            self.maghrib,
            self.isha,
        ]

    @property
    def is_fully_excused(self):
        """Excused days freeze the streak without increasing it."""
        return all(status == 'excused' for status in self.prayer_statuses)

    @property
    def counts_toward_streak_increment(self):
        """
        Returns True when the day should increment streak.
        All five prayers must be completed with valid streak statuses.
        """
        if self.is_fully_excused:
            return False

        valid_statuses = {'on_time', 'late', 'qada'}
        return all(
            completed and status in valid_statuses
            for completed, status in zip(self.prayer_completed, self.prayer_statuses)
        )

    @property
    def is_valid_for_streak(self):
        """Returns True when the day preserves streak continuity."""
        return self.is_fully_excused or self.counts_toward_streak_increment

    @property
    def has_qada(self):
        """Returns True if any prayer was prayed as Qada."""
        return any(status == 'qada' for status in self.prayer_statuses)

    @property
    def excused_count(self):
        """Returns count of prayers marked as excused."""
        return sum(1 for status in self.prayer_statuses if status == 'excused')


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

    def recalculate(self, force=False):
        """
        Recalculate streak data.

        Fully excused days keep the current streak alive without incrementing it.
        Pending or incomplete days do not count and will eventually break the chain.
        Recovery (protection) window: if a missed day has active protection, the chain
        stays alive so the user can still log Qada before the window closes.
        """
        from prayers.services.streak_service import get_recovery_status

        today = timezone.localdate()

        if not force and self.last_recalculated_at:
            last_calc_date = timezone.localtime(self.last_recalculated_at).date()
            if last_calc_date == today:
                return

        # Sprint 1: Sunday-based weekly reset for tokens (PRD)
        if self._is_new_week(self.tokens_reset_date):
            self.weekly_tokens_used = 0
            self.tokens_reset_date = self._current_week_start(today)

        current = 0
        longest = 0
        last_completed = None
        current_chain_count = 0
        previous_date = None
        chain_is_alive = False

        logs = DailyPrayerLog.objects.filter(user=self.user).order_by('date')
        for log in logs:
            if previous_date and (log.date - previous_date).days > 1:
                longest = max(longest, current_chain_count)
                current_chain_count = 0
                chain_is_alive = False

            if not log.is_valid_for_streak:
                # Check if protection is still active — chain stays alive during window
                recovery = get_recovery_status(log, self)
                if recovery['is_protected']:
                    # Protection active: preserve chain, don't increment
                    chain_is_alive = True
                    previous_date = log.date
                    continue
                # Protection expired or not available: break streak
                longest = max(longest, current_chain_count)
                current_chain_count = 0
                chain_is_alive = False
                previous_date = log.date
                continue

            chain_is_alive = True
            if log.counts_toward_streak_increment:
                current_chain_count += 1
                last_completed = log.date

            previous_date = log.date

        longest = max(longest, current_chain_count)

        if chain_is_alive and previous_date and (today - previous_date).days <= 1:
            current = current_chain_count

        self.current_streak = current
        self.longest_streak = longest
        self.last_completed_date = last_completed
        self.last_recalculated_at = timezone.now()
        self.save()

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

        yesterday = today - timezone.timedelta(days=1)
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
