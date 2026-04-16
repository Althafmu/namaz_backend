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

    def __str__(self):
        return f'{self.user.username} - {self.current_streak} day streak'

    @property
    def max_protector_tokens(self):
        return self.MAX_PROTECTOR_TOKENS

    @staticmethod
    def _current_week_start(target_date):
        return target_date - timedelta(days=target_date.weekday())

    def recalculate(self, force=False):
        """
        Recalculate streak data.

        Fully excused days keep the current streak alive without incrementing it.
        Pending or incomplete days do not count and will eventually break the chain.
        """
        today = timezone.localdate()

        if not force and self.last_recalculated_at:
            last_calc_date = timezone.localtime(self.last_recalculated_at).date()
            if last_calc_date == today:
                return

        current_week_start = self._current_week_start(today)
        if self.tokens_reset_date != current_week_start:
            if self.tokens_reset_date is not None:
                self.protector_tokens = self.MAX_PROTECTOR_TOKENS
            self.tokens_reset_date = current_week_start

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

    def consume_protector_token(self):
        """
        Consume a protector token to save streak.
        Returns True if token was consumed, False if none available.
        """
        if self.protector_tokens > 0:
            self.protector_tokens -= 1
            self.save(update_fields=['protector_tokens'])
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
