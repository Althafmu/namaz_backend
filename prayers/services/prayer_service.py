from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone

from prayers.models import DailyPrayerLog, Streak
from prayers.services.status_service import CanonicalPrayerStatus, canonical_to_db
from prayers.selectors import get_today_log
from prayers.utils.time_utils import get_effective_today

@transaction.atomic
def update_today_log(
    user,
    data: dict,
    target_date=None,
) -> DailyPrayerLog:
    """
    Update today's prayer log with validated data.
    """
    if target_date is None:
        target_date = get_effective_today()
    
    # Get the log for today
    log = DailyPrayerLog.objects.get(user=user, date=target_date)
    
    # Update using serializer for validation
    serializer = DailyPrayerLogSerializer(log, data=data, partial=True)
    if serializer.is_valid():
        updated_log = serializer.save()
        
        # Update streak
        streak, _ = Streak.objects.get_or_create(user=user)
        streak.recalculate(force=False, changed_date=target_date)
        
        # Attach recovery info
        attach_recovery_to_logs([updated_log], user)
        
        return updated_log
    else:
        raise ValueError(f"Validation error: {serializer.errors}")


@transaction.atomic
def log_prayer(
    user,
    prayer_name: str,
    completed: bool,
    in_jamaat: bool = False,
    location: str = 'home',
    reason: str = None,
    date_str: str = None,
    prayed_jumah: bool = False,
    request=None,
) -> DailyPrayerLog:
    """
    Service method to log a single prayer.
    All business logic is centralized here.
    """
    # Parse logged_at
    from prayers.services.prayer_status_service import classify_prayer_status
    from prayers.selectors import get_effective_today
    
    target_date = None
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError("Invalid date format. Expected YYYY-MM-DD.")
    else:
        target_date = get_effective_today()
    
    # Resolve status
    from prayers.services.prayer_status_service import classify_prayer_status
    if request and hasattr(request, 'data'):
        prayer_time_windows = request.data.get("prayer_time_windows")
        config = request.data.get("config", {})
        if prayer_time_windows:
            canonical_status = classify_prayer_status(
                prayer_name=prayer_name,
                logged_at=timezone.now(),
                prayer_time_windows=prayer_time_windows,
                config=config,
            )
            status = canonical_to_db(canonical_status)
        else:
            # Compatibility fallback
            status = "pending" if not completed else "on_time"
    else:
        status = "pending" if not completed else "on_time"
    
    # Get or create log (service owns creation)
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
        log.prayed_jumah = prayed_jumah
    
    log.full_clean()
    log.save()
    
    # Update streak
    streak, _ = Streak.objects.get_or_create(user=user)
    streak.recalculate(force=False, changed_date=target_date)
    
    # Attach recovery info
    from prayers.services.streak_service import attach_recovery_to_logs
    attach_recovery_to_logs([log], user)
    
    return log


@transaction.atomic
def undo_last_action(
    user,
    target_date=None,
) -> DailyPrayerLog:
    """
    Undo the last prayer action for a given date.
    Returns the updated log or None if no action to undo.
    """
    if target_date is None:
        target_date = get_effective_today() - timedelta(days=1)
    
    try:
        log = DailyPrayerLog.objects.get(user=user, date=target_date)
        # Reset all prayers to False (undo logic)
        log.fajr = False
        log.dhuhr = False
        log.asr = False
        log.maghrib = False
        log.isha = False
        log.fajr_status = 'pending'
        log.dhuhr_status = 'pending'
        log.asr_status = 'pending'
        log.maghrib_status = 'pending'
        log.isha_status = 'pending'
        log.location = 'home'
        log.save()
        
        # Update streak
        streak, _ = Streak.objects.get_or_create(user=user)
        streak.recalculate(force=False, changed_date=target_date)
        
        # Attach recovery info
        attach_recovery_to_logs([log], user)
        
        return log
    except DailyPrayerLog.DoesNotExist:
        return None


@transaction.atomic
def set_excused_day(
    user,
    target_date,
) -> DailyPrayerLog:
    """Mark a day as excused."""
    log, created = DailyPrayerLog.objects.get_or_create(
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
def clear_excused_day(
    user,
    target_date,
) -> DailyPrayerLog:
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
