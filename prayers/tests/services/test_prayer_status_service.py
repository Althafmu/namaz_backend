import pytest
from datetime import datetime
from django.utils import timezone

from prayers.services.prayer_status_service import classify_prayer_status
from prayers.services.status_service import CanonicalPrayerStatus


def _aware(dt_str):
    dt = datetime.fromisoformat(dt_str)
    return dt if timezone.is_aware(dt) else timezone.make_aware(dt)


@pytest.mark.django_db
def test_classifier_is_deterministic_for_same_input():
    windows = {
        "fajr": {
            "on_time_end": _aware("2026-04-18T05:30:00"),
            "late_end": _aware("2026-04-18T06:00:00"),
            "qada_end": _aware("2026-04-18T12:00:00"),
        }
    }
    logged_at = _aware("2026-04-18T05:20:00")
    one = classify_prayer_status("fajr", logged_at, windows, {})
    two = classify_prayer_status("fajr", logged_at, windows, {})
    assert one == two == CanonicalPrayerStatus.ONTIME


@pytest.mark.django_db
def test_isha_fixed_3am_cutoff_policy_qada_before_cutoff():
    windows = {
        "isha": {
            "start": _aware("2026-04-18T20:00:00"),
            "on_time_end": _aware("2026-04-18T22:00:00"),
            "late_end": _aware("2026-04-18T23:30:00"),
        }
    }
    logged_at = _aware("2026-04-19T02:59:00")
    status = classify_prayer_status("isha", logged_at, windows, {"isha_cutoff_policy": "fixed_3am"})
    assert status == CanonicalPrayerStatus.QADA


@pytest.mark.django_db
def test_isha_fixed_3am_cutoff_policy_missed_after_cutoff():
    windows = {
        "isha": {
            "start": _aware("2026-04-18T20:00:00"),
            "on_time_end": _aware("2026-04-18T22:00:00"),
            "late_end": _aware("2026-04-18T23:30:00"),
        }
    }
    logged_at = _aware("2026-04-19T03:01:00")
    status = classify_prayer_status("isha", logged_at, windows, {"isha_cutoff_policy": "fixed_3am"})
    assert status == CanonicalPrayerStatus.MISSED

