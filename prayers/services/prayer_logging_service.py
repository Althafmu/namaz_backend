from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any
from django.db import transaction
from django.utils import timezone

from prayers.models import DailyPrayerLog, Streak
from prayers.services.status_service import CanonicalPrayerStatus, canonical_to_db
from prayers.services.prayer_status_service import classify_prayer_status
from prayers.services.streak_service import attach_recovery_to_logs, recalculate_streak
from prayers.utils.time_utils import get_effective_today


def _validate_prayer_name(prayer_name: str) -> str:
    """Validate prayer name and return lowercase."""
    valid_names = {'fajr', 'dhuhr', 'asr', 'maghrib', 'isha'}
    normalized = str(prayer_name).strip().lower()
    if normalized not in valid_names:
        raise ValueError(f"Invalid prayer name: {prayer_name}")
    return normalized


def _validate_prayer_status(status: str) -> str:
    """Validate prayer status string."""
    valid_statuses = {'on_time', 'late', 'qada', 'missed', 'pending', 'excused'}
    if status not in valid_statuses:
        raise ValueError(f"Invalid prayer status: {status}")
    return status


@transaction.atomic
def log_prayer(
    user,
    prayer_name: str,
    completed: bool,
    status: Optional[str] = None,
    in_jamaat: bool = False,
    location: str = 'home',
    reason: Optional[str] = None,
    target_date: Optional[date] = None,
    prayer_time_windows: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> DailyPrayerLog:
    """
    Service method to log a single prayer.
    All business logic is centralized here.
    No request objects or DRF serializers used.
    """
    prayer_name = _validate_prayer_name(prayer_name)
    
    if target_date is None:
        target_date = get_effective_today()
    
    # Resolve status
    if status is None and prayer_time_windows:
        try:
            canonical_status = classify_prayer_status(
                prayer_name=prayer_name,
                logged_at=timezone.now(),
                prayer_time_windows=prayer_time_windows,
                config=config,
            )
            status = canonical_to_db(canonical_status)
        except (ValueError, KeyError):
            # Fallback if classification fails
            status = "pending" if not completed else "on_time"
    elif status is None:
        status = "pending" if not completed else "on_time"
    
    # Validate status
    status = _validate_prayer_status(status)
    
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
    setattr(log, fields[3], reason or '')
    log.location = location
    
    if prayer_name == 'dhuhr':
        # Handle prayed_jumah if provided (would need extra param)
        pass
    
    log.save()
    
    # Update streak
    streak, _ = Streak.objects.get_or_create(user=user)
    recalculate_streak(streak, force=False, changed_date=target_date)
    
    # Attach recovery info
    attach_recovery_to_logs([log], user)
    
    return log


@transaction.atomic
def update_today_log(
    user,
    validated_data: Dict[str, Any],
    target_date: Optional[date] = None,
) -> DailyPrayerLog:
    """
    Update today's prayer log with validated data.
    No serializer usage - direct field updates with targeted validation.
    """
    if target_date is None:
        target_date = get_effective_today()
    
    # Get the log for target date
    try:
        log = DailyPrayerLog.objects.get(user=user, date=target_date)
    except DailyPrayerLog.DoesNotExist:
        raise ValueError(f"No prayer log found for date {target_date}")
    
    # Define allowed fields for update
    allowed_fields = {
        'fajr', 'dhuhr', 'asr', 'maghrib', 'isha',
        'fajr_in_jamaat', 'dhuhr_in_jamaat', 'asr_in_jamaat',
        'maghrib_in_jamaat', 'isha_in_jamaat',
        'fajr_status', 'dhuhr_status', 'asr_status',
        'maghrib_status', 'isha_status',
        'fajr_reason', 'dhuhr_reason', 'asr_reason',
        'maghrib_reason', 'isha_reason',
        'location', 'prayed_jumah'
    }
    
    # Update fields directly
    for field, value in validated_data.items():
        if field not in allowed_fields:
            continue  # Skip unknown fields
        if field.endswith('_status'):
            value = _validate_prayer_status(value)
        setattr(log, field, value)
    
    log.save()
    
    # Update streak
    streak, _ = Streak.objects.get_or_create(user=user)
    recalculate_streak(streak, force=False, changed_date=target_date)
    
    # Attach recovery info
    attach_recovery_to_logs([log], user)
    
    return log
