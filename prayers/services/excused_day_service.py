from datetime import date
from typing import Optional
from django.db import transaction
from django.utils import timezone

from prayers.models import DailyPrayerLog, Streak
from prayers.services.streak_service import recalculate_streak


@transaction.atomic
def set_excused_day(
    user,
    target_date: date,
) -> DailyPrayerLog:
    """Mark a day as excused. Returns updated log."""
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
    recalculate_streak(streak, force=False, changed_date=target_date)
    
    return log


@transaction.atomic
def clear_excused_day(
    user,
    target_date: date,
) -> Optional[DailyPrayerLog]:
    """Clear excused status for a day. Returns updated log or None."""
    try:
        log = DailyPrayerLog.objects.get(user=user, date=target_date)
        log.fajr_status = 'pending'
        log.dhuhr_status = 'pending'
        log.asr_status = 'pending'
        log.maghrib_status = 'pending'
        log.isha_status = 'pending'
        log.save()
        
        streak, _ = Streak.objects.get_or_create(user=user)
        recalculate_streak(streak, force=False, changed_date=target_date)
        return log
    except DailyPrayerLog.DoesNotExist:
        return None
