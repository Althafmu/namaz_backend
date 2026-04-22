from django.conf import settings
from django.db import models
from django.utils import timezone


class SunnahLog(models.Model):
    PRAYER_TYPE_CHOICES = [
        ('fajr', 'Fajr Sunnah'),
        ('dhuhr_before', 'Dhuhr Sunnah (2 Before)'),
        ('dhuhr_after', 'Dhuhr Sunnah (2 After)'),
        ('asr', 'Asr Sunnah'),
        ('maghrib', 'Maghrib Sunnah'),
        ('isha', 'Isha Sunnah'),
        ('witr', 'Witr'),
        ('dhuha', 'Dhuha'),
        ('tahajjud', 'Tahajjud'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sunnah_logs',
    )
    date = models.DateField(default=timezone.localdate)
    prayer_type = models.CharField(max_length=20, choices=PRAYER_TYPE_CHOICES)
    completed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'date', 'prayer_type')
        ordering = ['-date', 'prayer_type']
        indexes = [
            models.Index(fields=['user', 'date'], name='sunnahlog_user_date_idx'),
        ]

    def __str__(self):
        return f'{self.user.username} {self.date} {self.prayer_type}={self.completed}'
