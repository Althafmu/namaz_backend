from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count, Case, When, IntegerField, F
from prayers.models import DailyPrayerLog, Streak

def get_today_log(user, target_date=None):
    """Get or create today's prayer log for a user."""
    if target_date is None:
        target_date = timezone.localdate()
    log, created = DailyPrayerLog.objects.get_or_create(
        user=user,
        date=target_date,
    )
    return log, created


def get_prayer_history(user, days=7, page=1, page_size=30):
    """Get prayer history with pagination."""
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
    """Get detailed prayer history statistics."""
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
    """Get summary of reasons for missed prayers."""
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
    """Get sync status for a user."""
    from prayers.models import UserSettings
    settings, _ = UserSettings.objects.get_or_create(user=user)
    streak, _ = Streak.objects.get_or_create(user=user)
    
    return {
        'settings': settings,
        'streak': streak,
        'last_sync': streak.last_recalculated_at,
    }
