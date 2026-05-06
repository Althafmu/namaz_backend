from datetime import timedelta, date
from typing import Optional
from django.db import transaction
from django.utils import timezone

from prayers.models import DailyPrayerLog, Streak
from prayers.services.streak_service import attach_recovery_to_logs, recalculate_streak
from prayers.utils.time_utils import get_effective_today


@transaction.atomic
def undo_last_action(
    user,
    target_date: Optional[date] = None,
) -> Optional[DailyPrayerLog]:
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
        recalculate_streak(streak, force=False, changed_date=target_date)
        
        # Attach recovery info
        attach_recovery_to_logs([log], user)
        
        return log
    except DailyPrayerLog.DoesNotExist:
        return None
