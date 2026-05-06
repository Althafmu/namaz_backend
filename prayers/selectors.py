from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count, Case, When, IntegerField, F
from prayers.models import DailyPrayerLog, Streak

def get_today_log(user, target_date=None):
    """Get today's prayer log for a user (read-only)."""
    if target_date is None:
        target_date = timezone.localdate()
    try:
        log = DailyPrayerLog.objects.get(
            user=user,
            date=target_date,
        )
        return log, False  # False = not created
    except DailyPrayerLog.DoesNotExist:
        return None, False  # None = not found


def get_prayer_history(user, days=7, page=1, page_size=30):
    """Get prayer history with pagination (read-only)."""
    today = timezone.localdate()
    start_date = today - timezone.timedelta(days=days - 1)
    
    logs = DailyPrayerLog.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=today,
    ).order_by('-date')
    
    total_count = logs.count()
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    page = max(1, page)
    
    offset = (page - 1) * page_size
    logs_page = logs[offset:offset + page_size]
    
    return {
        'results': logs_page,
        'count': total_count,
        'page': page,
        'total_pages': total_pages,
        'page_size': page_size,
    }


def get_detailed_prayer_history(user, days=30):
    """Get detailed prayer history statistics (read-only)."""
    today = timezone.localdate()
    start_date = today - timezone.timedelta(days=days - 1)
    
    logs = DailyPrayerLog.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=today,
    ).order_by('-date')
    
    # Calculate statistics
    total_days = logs.count()
    completed_days = logs.filter(
        fajr=True,
        dhuhr=True,
        asr=True,
        maghrib=True,
        isha=True,
    ).count()
    
    return {
        'logs': logs,
        'total_days': total_days,
        'completed_days': completed_days,
        'completion_rate': (completed_days / total_days * 100) if total_days > 0 else 0,
    }


def get_reason_summary(user, days=30):
    """Get summary of reasons for missed prayers (read-only)."""
    today = timezone.localdate()
    start_date = today - timezone.timedelta(days=days - 1)
    
    logs = DailyPrayerLog.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=today,
    )
    
    # Aggregate reasons
    reason_counts = logs.values('fajr_reason', 'dhuhr_reason', 'asr_reason', 'maghrib_reason', 'isha_reason').annotate(
        count=Count('id')
    )
    
    return reason_counts


def get_sync_status(user):
    """Get sync status for a user (read-only)."""
    from prayers.models import UserSettings
    try:
        settings = UserSettings.objects.get(user=user)
    except UserSettings.DoesNotExist:
        settings = None
    
    try:
        streak = Streak.objects.get(user=user)
    except Streak.DoesNotExist:
        streak = None
    
    return {
        'settings': settings,
        'streak': streak,
        'last_sync': streak.last_recalculated_at if streak else None,
    }
