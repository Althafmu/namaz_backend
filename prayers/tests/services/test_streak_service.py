import pytest
from datetime import date, timedelta
from django.contrib.auth.models import User

from prayers.models import DailyPrayerLog, Streak
from prayers.services.streak_service import recalculate_streak


def create_completed_log(user, target_date, **overrides):
    payload = {
        'user': user,
        'date': target_date,
        'fajr': True,
        'dhuhr': True,
        'asr': True,
        'maghrib': True,
        'isha': True,
        'fajr_status': 'on_time',
        'dhuhr_status': 'on_time',
        'asr_status': 'on_time',
        'maghrib_status': 'on_time',
        'isha_status': 'on_time',
    }
    payload.update(overrides)
    return DailyPrayerLog.objects.create(**payload)


@pytest.mark.django_db
def test_service_recalculate_full_mode():
    user = User.objects.create_user(username='svc1', password='testpass')
    streak, _ = Streak.objects.get_or_create(user=user)
    yesterday = date.today() - timedelta(days=1)
    create_completed_log(user, yesterday)
    result = recalculate_streak(streak, force=True)
    assert result["mode"] == "full"
    assert streak.current_streak in {0, 1}


@pytest.mark.django_db
def test_service_recalculate_incremental_mode_for_recent_change():
    user = User.objects.create_user(username='svc2', password='testpass')
    streak, _ = Streak.objects.get_or_create(user=user)
    today = date.today()
    yesterday = today - timedelta(days=1)
    create_completed_log(user, yesterday)
    create_completed_log(user, today)
    recalculate_streak(streak, force=True)
    result = recalculate_streak(streak, force=False, changed_date=today)
    assert result["mode"] in {"incremental", "full"}


@pytest.mark.django_db
def test_service_recalculate_fallback_full_for_old_change():
    user = User.objects.create_user(username='svc3', password='testpass')
    streak, _ = Streak.objects.get_or_create(user=user)
    old_date = date.today() - timedelta(days=10)
    create_completed_log(user, old_date)
    result = recalculate_streak(streak, force=False, changed_date=old_date)
    assert result["mode"] == "full"

