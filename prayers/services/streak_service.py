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
    2. Before next 3 AM cutoff (window is from missed time → next cutoff)
    3. User has available tokens (protector_tokens > 0)

    Returns per-prayer dict so frontend can show which specific prayer needs Qada:
    {
        "fajr": {"is_protected": bool, "expires_at": str|None, "requires_qada": bool},
        ...
    }

    Single source of truth — called from both view (to attach to objects)
    and serializer (to read pre-computed value).
    """
    if prayer_log is None or streak is None:
        return {k: {'is_protected': False, 'expires_at': None, 'requires_qada': False}
                for k in ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']}

    prayer_keys = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']
    now = timezone.now()
    cutoff_next = get_cutoff_datetime_for_date(prayer_log.date)

    # Token eligibility: just check if tokens available, not cooldown/consumption rules
    # Recovery eligibility ≠ token consumption eligibility
    has_tokens = streak.protector_tokens > 0

    result = {}
    # Only protect the LATEST missed prayer (token economy: one token = one prayer)
    # Prayer order: fajr < dhuhr < asr < maghrib < isha
    missed_prayers = [key for key in prayer_keys
                      if getattr(prayer_log, f'{key}_status') == 'missed']
    latest_missed = missed_prayers[-1] if missed_prayers else None

    for key in prayer_keys:
        status = getattr(prayer_log, f'{key}_status')
        if status == 'missed':
            within_window = now < cutoff_next
            is_protected = (key == latest_missed) and within_window and has_tokens

            if is_protected:
                result[key] = {
                    'is_protected': True,
                    'expires_at': cutoff_next.isoformat(),
                    'requires_qada': True,
                }
            else:
                result[key] = {
                    'is_protected': False,
                    'expires_at': None,
                    'requires_qada': False,
                }
        else:
            result[key] = {
                'is_protected': False,
                'expires_at': None,
                'requires_qada': False,
            }

    return result


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
