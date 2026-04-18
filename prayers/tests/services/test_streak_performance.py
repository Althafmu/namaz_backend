import pytest
from datetime import date, timedelta
from django.contrib.auth.models import User

from prayers.models import DailyPrayerLog, Streak
from prayers.services.streak_service import recalculate_streak


def _create_log(user, d):
    return DailyPrayerLog.objects.create(
        user=user,
        date=d,
        fajr=True,
        dhuhr=True,
        asr=True,
        maghrib=True,
        isha=True,
        fajr_status='on_time',
        dhuhr_status='on_time',
        asr_status='on_time',
        maghrib_status='on_time',
        isha_status='on_time',
    )


@pytest.mark.django_db
@pytest.mark.slow
@pytest.mark.performance
def test_incremental_recalculation_processes_fewer_logs_for_recent_change():
    user = User.objects.create_user(username='perfuser', password='testpass')
    streak, _ = Streak.objects.get_or_create(user=user)
    today = date.today()

    for i in range(400):
        _create_log(user, today - timedelta(days=400 - i))

    full_result = recalculate_streak(streak, force=True)
    incremental_result = recalculate_streak(streak, force=False, changed_date=today)
    assert full_result["processed_logs"] >= incremental_result["processed_logs"]

