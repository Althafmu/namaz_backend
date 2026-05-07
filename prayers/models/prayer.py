from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

from prayers.services.status_service import is_completion_status_db


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
    prayed_jumah = models.BooleanField(default=False, help_text='If True, indicates the Friday noon prayer was Jumah instead of Dhuhr.')
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
        indexes = [
            models.Index(fields=['user', 'created_at'], name='prayerlog_user_created_idx'),
        ]
    
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
        return all(
            completed and is_completion_status_db(status)
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
