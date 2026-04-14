from django.db import models
from django.conf import settings
from django.utils import timezone


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

    # Status and reason per prayer
    STATUS_CHOICES = [
        ('on_time', 'On Time'),
        ('late', 'Late'),
        ('missed', 'Missed'),
    ]
    fajr_status = models.CharField(max_length=20, default='on_time', choices=STATUS_CHOICES)
    fajr_reason = models.CharField(max_length=255, blank=True, null=True)
    dhuhr_status = models.CharField(max_length=20, default='on_time', choices=STATUS_CHOICES)
    dhuhr_reason = models.CharField(max_length=255, blank=True, null=True)
    asr_status = models.CharField(max_length=20, default='on_time', choices=STATUS_CHOICES)
    asr_reason = models.CharField(max_length=255, blank=True, null=True)
    maghrib_status = models.CharField(max_length=20, default='on_time', choices=STATUS_CHOICES)
    maghrib_reason = models.CharField(max_length=255, blank=True, null=True)
    isha_status = models.CharField(max_length=20, default='on_time', choices=STATUS_CHOICES)
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
        return f"{self.user.username} — {self.date} — {completed}/5"

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
            self.fajr_in_jamaat, self.dhuhr_in_jamaat, self.asr_in_jamaat,
            self.maghrib_in_jamaat, self.isha_in_jamaat,
        ])


class Streak(models.Model):
    """Tracks continuous prayer streak for a user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='streak',
    )
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_completed_date = models.DateField(null=True, blank=True)
    last_recalculated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} — {self.current_streak} day streak"

    def recalculate(self, force=False):
        """
        Recalculate streak data.
        Optimized: Only performs full recalculation when necessary.

        Args:
            force: If True, always recalculate. If False, skip if already
                   calculated today (stale data is fine for same-day requests).
        """
        today = timezone.localdate()

        # Skip recalculation if already done today (unless forced)
        if not force and self.last_recalculated_at:
            last_calc_date = timezone.localtime(self.last_recalculated_at).date()
            if last_calc_date == today:
                return  # Already calculated today, cached data is fine

        # Single query: get all dates where ALL 5 prayers are completed
        # Uses database-level filtering instead of Python iteration
        complete_dates = list(
            DailyPrayerLog.objects.filter(
                user=self.user,
                fajr=True,
                dhuhr=True,
                asr=True,
                maghrib=True,
                isha=True,
            )
            .order_by('date')
            .values_list('date', flat=True)
        )

        # Reset everything
        current = 0
        longest = 0
        last_completed = None

        if complete_dates:
            current = 1
            last_completed = complete_dates[0]

            for i in range(1, len(complete_dates)):
                delta = (complete_dates[i] - complete_dates[i - 1]).days
                if delta == 1:
                    current += 1
                elif delta > 1:
                    # Gap detected — record longest and reset
                    longest = max(longest, current)
                    current = 1
                # delta == 0 shouldn't happen (unique_together), but ignore it

                last_completed = complete_dates[i]

            longest = max(longest, current)

            # Check gap from last completed date to today
            gap = (today - last_completed).days
            if gap > 1:
                # Streak is broken — missed at least one day
                current = 0

        self.current_streak = current
        self.longest_streak = longest
        self.last_completed_date = last_completed
        self.last_recalculated_at = timezone.now()
        self.save()

    def get_display_streak(self):
        """
        Returns the streak to display to the user.
        During the first 12 hours of the day (midnight to noon),
        shows the previous streak even if broken, for motivation.
        """
        now = timezone.localtime()
        hour = now.hour
        today = now.date()

        # If streak is alive, always show it
        if self.current_streak > 0:
            return self.current_streak

        # If after noon, show the actual streak (0 if broken)
        if hour >= 12:
            return self.current_streak

        # Before noon: show motivation streak
        # Calculate what the streak would be if counting backwards from yesterday
        if not self.last_completed_date:
            return 0

        # If last completed was yesterday, count the streak up to yesterday
        yesterday = today - timezone.timedelta(days=1)
        if self.last_completed_date == yesterday:
            # The streak broke today - show what it was before
            # Count complete days backwards from yesterday using optimized query
            complete_dates = list(
                DailyPrayerLog.objects.filter(
                    user=self.user,
                    fajr=True,
                    dhuhr=True,
                    asr=True,
                    maghrib=True,
                    isha=True,
                    date__lte=yesterday,
                )
                .order_by('-date')
                .values_list('date', flat=True)
            )
            if not complete_dates:
                return 0

            # Count consecutive days backwards
            streak_count = 1
            prev_date = complete_dates[0]
            for i in range(1, len(complete_dates)):
                gap = (prev_date - complete_dates[i]).days
                if gap == 1:
                    streak_count += 1
                    prev_date = complete_dates[i]
                else:
                    break
            return streak_count

        # Last completed was before yesterday - streak is genuinely broken
        return self.current_streak
