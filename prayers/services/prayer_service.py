from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone

from prayers.models import DailyPrayerLog, Streak
from prayers.services.status_service import CanonicalPrayerStatus, canonical_to_db
from prayers.selectors import get_today_log, get_prayer_history
from prayers.utils.time_utils import get_effective_today

@transaction.atomic
def log_prayer(user, prayer_name, completed, in_jamaat=False, location='home', reason=None, date_str=None, logged_at=None, prayer_time_windows=None, config=None):
    """
    Service method to log a single prayer.
    All business logic is centralized here.
    """
    # Parse logged_at
    if logged_at:
        if isinstance(logged_at, str):
            try:
                dt = datetime.fromisoformat(logged_at)
                logged_at = dt if timezone.is_aware(dt) else timezone.make_aware(dt)
            except ValueError:
                raise ValueError("Invalid logged_at format. Expected ISO datetime.")
        else:
            raise ValueError("logged_at must be an ISO datetime string.")
    else:
        logged_at = timezone.now()
    
    # Resolve status
    from prayers.services.prayer_status_service import classify_prayer_status
    if prayer_time_windows:
        canonical_status = classify_prayer_status(
            prayer_name=prayer_name,
            logged_at=logged_at,
            prayer_time_windows=prayer_time_windows,
            config=config or {},
        )
        status = canonical_to_db(canonical_status)
    else:
        # Compatibility fallback
        status = _resolve_status_from_request(prayer_name, completed, reason)
    
    # Get or create log
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else get_effective_today()
    log, created = DailyPrayerLog.objects.get_or_create(
        user=user,
        date=target_date,
    )
    
    # Update prayer fields
    prayer_field_map = {
        'fajr': ('fajr', 'fajr_in_jamaat', 'fajr_status', 'fajr_reason'),
        'dhuhr': ('dhuhr', 'dhuhr_in_jamaat', 'dhuhr_status', 'dhuhr_reason'),
        'asr': ('asr', 'asr_in_jamaat', 'asr_status', 'asr_reason'),
        'maghrib': ('maghrib', 'maghrib_in_jamaat', 'maghrib_status', 'maghrib_reason'),
        'isha': ('isha', 'isha_in_jamaat', 'isha_status', 'isha_reason'),
    }
    
    fields = prayer_field_map.get(prayer_name)
    if not fields:
        raise ValueError(f"Invalid prayer name: {prayer_name}")
    
    setattr(log, fields[0], completed)
    setattr(log, fields[1], in_jamaat)
    setattr(log, fields[2], status)
    setattr(log, fields[3], reason)
    log.location = location
    
    if prayer_name == 'dhuhr':
        log.prayed_jumah = in_jamaat
    
    log.full_clean()
    log.save()
    
    # Update streak
    streak, _ = Streak.objects.get_or_create(user=user)
    streak.recalculate(force=False, changed_date=target_date)
    
    # Attach recovery info
    from prayers.services.streak_service import attach_recovery_to_logs
    attach_recovery_to_logs([log], user)
    
    return log


def _resolve_status_from_request(prayer_name, completed, reason):
    """Helper to resolve status from request (compatibility)."""
    from prayers.services.status_service import CanonicalPrayerStatus
    if not completed:
        return CanonicalPrayerStatus.MISSED
    
    # This is simplified - in reality, you'd check time windows
    return CanonicalPrayerStatus.ONTIME


@transaction.atomic
def set_excused_day(user, target_date):
    """Mark a day as excused."""
    log, _ = DailyPrayerLog.objects.get_or_create(
        user=user,
        date=target_date,
    )
    
    # Set all prayers to excused
    log.fajr_status = 'excused'
    log.dhuhr_status = 'excused'
    log.asr_status = 'excused'
    log.maghrib_status = 'excused'
    log.isha_status = 'excused'
    log.save()
    
    # Update streak (excused days freeze streak)
    streak, _ = Streak.objects.get_or_create(user=user)
    streak.recalculate(force=False, changed_date=target_date)
    
    return log


@transaction.atomic
def clear_excused_day(user, target_date):
    """Clear excused status for a day."""
    try:
        log = DailyPrayerLog.objects.get(user=user, date=target_date)
        log.fajr_status = 'pending'
        log.dhuhr_status = 'pending'
        log.asr_status = 'pending'
        log.maghrib_status = 'pending'
        log.isha_status = 'pending'
        log.save()
        
        streak, _ = Streak.objects.get_or_create(user=user)
        streak.recalculate(force=False, changed_date=target_date)
        return log
    except DailyPrayerLog.DoesNotExist:
        return None
