from django.urls import path

from sunnah.views import sunnah_daily_view, sunnah_log_view, sunnah_weekly_view

urlpatterns = [
    path('log/', sunnah_log_view, name='sunnah-log'),
    path('daily/', sunnah_daily_view, name='sunnah-daily'),
    path('weekly/', sunnah_weekly_view, name='sunnah-weekly'),
]
