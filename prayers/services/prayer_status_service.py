from __future__ import annotations

from datetime import datetime, time

from django.utils import timezone

from prayers.services.status_service import CanonicalPrayerStatus


def _as_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if timezone.is_aware(value) else timezone.make_aware(value)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
        return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
    raise ValueError("Expected datetime or ISO datetime string.")


def _resolve_isha_qada_cutoff(prayer_name, prayer_window, config, logged_at):
    explicit = _as_datetime(prayer_window.get("qada_end"))
    if explicit is not None:
        return explicit

    policy = (config or {}).get("isha_cutoff_policy", "fixed_3am")
    if prayer_name != "isha":
        return None
    if policy != "fixed_3am":
        raise ValueError("Unsupported isha_cutoff_policy. Supported: fixed_3am")

    start_dt = _as_datetime(prayer_window.get("start"))
    anchor_local_date = timezone.localtime(start_dt or logged_at).date()
    return timezone.make_aware(datetime.combine(anchor_local_date, time.min)) + timezone.timedelta(days=1, hours=3)


def classify_prayer_status(prayer_name, logged_at, prayer_time_windows, config=None):
    """
    Deterministic status classifier.

    Inputs:
      - prayer_name: one of fajr|dhuhr|asr|maghrib|isha
      - logged_at: timezone-aware datetime (or ISO string)
      - prayer_time_windows: dict keyed by prayer name with window datetimes
      - config: optional dict (supports isha_cutoff_policy=fixed_3am)

    Rule order:
      1) <= on_time_end -> ONTIME
      2) <= late_end -> LATE
      3) <= qada_end -> QADA
      4) otherwise -> MISSED

    Isha cutoff policy (explicit):
      If qada_end is absent for Isha, qada cutoff defaults to next local day 03:00.
    """
    prayer_key = str(prayer_name).strip().lower()
    if prayer_key not in {"fajr", "dhuhr", "asr", "maghrib", "isha"}:
        raise ValueError("Invalid prayer_name.")

    if not isinstance(prayer_time_windows, dict):
        raise ValueError("prayer_time_windows must be a dict.")

    logged_at_dt = _as_datetime(logged_at)
    if logged_at_dt is None:
        raise ValueError("logged_at is required.")

    prayer_window = prayer_time_windows.get(prayer_key)
    if not isinstance(prayer_window, dict):
        raise ValueError("Missing prayer window for selected prayer.")

    on_time_end = _as_datetime(prayer_window.get("on_time_end") or prayer_window.get("end"))
    late_end = _as_datetime(prayer_window.get("late_end"))
    qada_end = _resolve_isha_qada_cutoff(prayer_key, prayer_window, config, logged_at_dt)
    if qada_end is None:
        qada_end = _as_datetime(prayer_window.get("qada_end"))

    if on_time_end is None or late_end is None:
        raise ValueError("prayer_time_windows must include on_time_end/end and late_end.")

    if logged_at_dt <= on_time_end:
        return CanonicalPrayerStatus.ONTIME
    if logged_at_dt <= late_end:
        return CanonicalPrayerStatus.LATE
    if qada_end and logged_at_dt <= qada_end:
        return CanonicalPrayerStatus.QADA
    return CanonicalPrayerStatus.MISSED

