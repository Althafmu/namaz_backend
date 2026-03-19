from django.contrib import admin
from .models import DailyPrayerLog, Streak


@admin.register(DailyPrayerLog)
class DailyPrayerLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'fajr', 'dhuhr', 'asr', 'maghrib', 'isha', 'completed_count')
    list_filter = ('date', 'user')
    search_fields = ('user__username',)
    ordering = ('-date',)


@admin.register(Streak)
class StreakAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_streak', 'longest_streak', 'last_completed_date')
    search_fields = ('user__username',)
