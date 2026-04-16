"""
Streak service — single source of truth for streak logic.

Architecture:
    View → Service → Model
    Serializer is DUMB (formatting only)

All recovery status computation lives here.
"""

from datetime import timedelta

from django.utils import timezone


def get_cutoff_for_date(target_date):
    """
    Returns the 3 AM cutoff date for a given prayer date.
    The cutoff for prayers on date X is 3 AM on date X+1.
    """
    return target_date + timedelta(days=1)


def get_cutoff_datetime_for_date(target_date):
    """
    Returns the 3 AM datetime for the day after target_date.
    """
    return timezone.make_aware(
        timezone.datetime.combine(
            get_cutoff_for_date(target_date),
            timezone.datetime.min.time()
        )
    ) + timedelta(hours=3)


def get_recovery_status(prayer_log, streak):
    """
    Returns recovery state for a single DailyPrayerLog.

    Recovery is active when ALL of these are true:
    1. Prayer is missed
    2. Within 24h of 3 AM cutoff (i.e., before next cutoff)
    3. User has available tokens (can_use_token returns allowed)

    Returns dict:
        {
            "is_protected": bool,
            "expires_at": ISO string or None,
            "requires_qada": bool,
        }

    Single source of truth — called from both view (to attach to objects)
    and serializer (to read pre-computed value).
    """
    if prayer_log is None or streak is None:
        return {'is_protected': False, 'expires_at': None, 'requires_qada': False}

    # Find which prayer(s) are missed on this log
    prayer_keys = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']
    missed_prayers = [
        key for key in prayer_keys
        if getattr(prayer_log, f'{key}_status') == 'missed'
    ]

    if not missed_prayers:
        return {'is_protected': False, 'expires_at': None, 'requires_qada': False}

    # Recovery window: from cutoff of missed day, up to next cutoff (24h)
    # Window = from 3am next day to 3am the day after = exactly 24h
    cutoff_today = get_cutoff_datetime_for_date(prayer_log.date)
    cutoff_next = cutoff_today + timedelta(days=1)

    now = timezone.now()
    within_window = cutoff_today <= now < cutoff_next

    # Check token availability using the model's can_use_token method
    can_use = streak.can_use_token()
    has_tokens = can_use['allowed']

    # Protection only when within window AND has tokens
    is_protected = within_window and has_tokens

    if is_protected:
        return {
            'is_protected': True,
            'expires_at': cutoff_next.isoformat(),
            'requires_qada': True,
        }

    return {
        'is_protected': False,
        'expires_at': cutoff_next.isoformat() if within_window else None,
        'requires_qada': False,
    }


def attach_recovery_to_logs(logs, user):
    """
    Bulk-attach recovery status to a queryset of DailyPrayerLogs.
    Pre-computes recovery per log to avoid N+1 queries.
    """
    from prayers.models import Streak

    try:
        streak = Streak.objects.get(user=user)
    except Streak.DoesNotExist:
        streak = None

    for log in logs:
        log.recovery = get_recovery_status(log, streak)
