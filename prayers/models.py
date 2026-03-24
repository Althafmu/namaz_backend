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
    date = models.DateField(default=timezone.now)

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

    def __str__(self):
        return f"{self.user.username} — {self.current_streak} day streak"

    def update_streak(self, completed_date):
        """
        Call this after a user completes all 5 prayers for a day.
        Handles streak increment, reset, and longest tracking.
        """

        if self.last_completed_date is None:
            # First completed day ever
            self.current_streak = 1
        elif completed_date == self.last_completed_date:
            # Already counted this day
            return
        elif (completed_date - self.last_completed_date).days == 1:
            # Consecutive day — increment streak
            self.current_streak += 1
        elif (completed_date - self.last_completed_date).days > 1:
            # Missed day(s) — reset streak
            self.current_streak = 1

        self.last_completed_date = completed_date
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
        self.save()

    def check_and_reset(self):
        """Reset streak if user missed yesterday entirely."""
        today = timezone.now().date()
        if self.last_completed_date and (today - self.last_completed_date).days > 1:
            self.current_streak = 0
            self.save()
