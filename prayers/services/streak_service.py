"""Streak service — single source of truth for streak logic."""

from datetime import timedelta

from django.utils import timezone

from prayers.services.status_service import is_completion_status_db
from prayers.utils.time_utils import get_effective_today


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
        return {k: {'is_protected': False, 'expires_at': None, 'requires_qada': False, 'is_expired': False}
                for k in ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']}

    # Phase 3: Cross-day constraint — recovery only for current day (no cross-day ambiguity)
    if prayer_log.date != get_effective_today():
        return {k: {'is_protected': False, 'expires_at': None, 'requires_qada': False, 'is_expired': False}
                for k in ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']}

    prayer_keys = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']
    now = timezone.now()
    cutoff_next = get_cutoff_datetime_for_date(prayer_log.date)

    # Token eligibility: just check if tokens available, not cooldown/consumption rules
    # Recovery eligibility ≠ token consumption eligibility
    has_tokens = streak.protector_tokens > 0

    result = {}
    # Phase 3: Priority recovery — protect highest-priority missed prayer (Fajr first)
    # Prevents wrong allocation when multiple prayers are missed
    missed_prayers = [key for key in prayer_keys
                      if getattr(prayer_log, f'{key}_status') == 'missed']
    priority_order = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']
    priority_missed = [p for p in priority_order if p in missed_prayers]
    target_prayer = priority_missed[0] if priority_missed else None

    for key in prayer_keys:
        status = getattr(prayer_log, f'{key}_status')
        if status == 'missed':
            within_window = now < cutoff_next
            is_protected = (key == target_prayer) and within_window and has_tokens

            if is_protected:
                result[key] = {
                    'is_protected': True,
                    'expires_at': cutoff_next.isoformat(),
                    'requires_qada': True,
                    'is_expired': False,
                }
            elif not within_window:
                result[key] = {
                    'is_protected': False,
                    'expires_at': None,
                    'requires_qada': False,
                    'is_expired': True,
                }
            else:
                result[key] = {
                    'is_protected': False,
                    'expires_at': None,
                    'requires_qada': False,
                    'is_expired': False,
                }
        else:
            result[key] = {
                'is_protected': False,
                'expires_at': None,
                'requires_qada': False,
                'is_expired': False,
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


def _apply_weekly_reset(streak, today):
    if streak._is_new_week(streak.tokens_reset_date):
        streak.weekly_tokens_used = 0
        streak.tokens_reset_date = streak._current_week_start(today)


def _full_recalculate(streak, force=False):
    today = timezone.localdate()

    if not force and streak.last_recalculated_at:
        last_calc_date = timezone.localtime(streak.last_recalculated_at).date()
        if last_calc_date == today:
            return {"mode": "skipped", "processed_logs": 0}

    _apply_weekly_reset(streak, today)

    from prayers.models import DailyPrayerLog

    current = 0
    longest = 0
    last_completed = None
    current_chain_count = 0
    previous_date = None
    chain_is_alive = False
    processed = 0

    logs = DailyPrayerLog.objects.filter(user=streak.user).order_by('date')
    for log in logs:
        processed += 1
        if previous_date and (log.date - previous_date).days > 1:
            longest = max(longest, current_chain_count)
            current_chain_count = 0
            chain_is_alive = False

        if not log.is_valid_for_streak:
            recovery = get_recovery_status(log, streak)
            any_protected = any(v['is_protected'] for v in recovery.values())
            if any_protected:
                chain_is_alive = True
                previous_date = log.date
                continue
            longest = max(longest, current_chain_count)
            current_chain_count = 0
            chain_is_alive = False
            previous_date = log.date
            continue

        chain_is_alive = True
        if log.counts_toward_streak_increment:
            current_chain_count += 1
            last_completed = log.date

        previous_date = log.date

    longest = max(longest, current_chain_count)

    if chain_is_alive and previous_date and (today - previous_date).days <= 1:
        current = current_chain_count

    streak.current_streak = current
    streak.longest_streak = longest
    streak.last_completed_date = last_completed
    streak.last_recalculated_at = timezone.now()
    streak.save()
    return {"mode": "full", "processed_logs": processed}


def _incremental_recalculate_recent(streak, changed_date):
    """
    Incremental path for recent updates.

    This scans backward from today until chain break to compute current streak.
    If the change is older than 2 days, we fall back to full recalculation.
    """
    today = timezone.localdate()
    if changed_date is None:
        return _full_recalculate(streak, force=False)

    if (today - changed_date).days > 2:
        return _full_recalculate(streak, force=True)

    _apply_weekly_reset(streak, today)
    from prayers.models import DailyPrayerLog

    logs = DailyPrayerLog.objects.filter(user=streak.user, date__lte=today).order_by('-date')
    processed = 0
    current_chain_count = 0
    chain_is_alive = False
    previous_date = None
    last_completed = streak.last_completed_date

    for log in logs:
        processed += 1
        if previous_date and (previous_date - log.date).days > 1:
            break

        if not log.is_valid_for_streak:
            recovery = get_recovery_status(log, streak)
            any_protected = any(v['is_protected'] for v in recovery.values())
            if any_protected:
                chain_is_alive = True
                previous_date = log.date
                continue
            break

        chain_is_alive = True
        if log.counts_toward_streak_increment:
            current_chain_count += 1
            if last_completed is None or log.date > last_completed:
                last_completed = log.date
        previous_date = log.date

    current = current_chain_count if chain_is_alive else 0
    streak.current_streak = current
    streak.longest_streak = max(streak.longest_streak, current)
    streak.last_completed_date = last_completed
    streak.last_recalculated_at = timezone.now()
    streak.save()
    return {"mode": "incremental", "processed_logs": processed}


def recalculate_streak(streak, force=False, changed_date=None):
    if force:
        return _full_recalculate(streak, force=True)
    return _incremental_recalculate_recent(streak, changed_date)


def counts_toward_streak_increment(log):
    if log.is_fully_excused:
        return False
    return all(
        completed and is_completion_status_db(status)
        for completed, status in zip(log.prayer_completed, log.prayer_statuses)
    )
