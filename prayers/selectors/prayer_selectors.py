def get_today_log(user, target_date=None):
    """Get today's prayer log for a user (read-only). Returns (log, created_bool)."""
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


def get_prayer_history_queryset(user, days=7):
    """Return QuerySet of prayer logs for N days. No pagination semantics."""
    today = timezone.localdate()
    start_date = today - timedelta(days=days - 1)
    
    return DailyPrayerLog.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=today,
    ).order_by('-date')
    # Returns QuerySet - caller decides pagination


def get_detailed_prayer_history(user, year=None, month=None, days=30, page=1, page_size=30):
    """Get detailed prayer history statistics (read-only). Returns dict with paginated results."""
    from datetime import date

    today = timezone.localdate()

    if year and month:
        try:
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
        except ValueError:
            start_date = today - timedelta(days=days - 1)
            end_date = today
    else:
        start_date = today - timedelta(days=days - 1)
        end_date = today

    logs = DailyPrayerLog.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=end_date,
    ).order_by('-date')

    total_count = logs.count()
    total_pages = (total_count + page_size - 1) // page_size
    offset = (page - 1) * page_size
    paginated_logs = logs[offset:offset + page_size]

    from prayers.serializers import DailyPrayerLogSerializer
    serializer = DailyPrayerLogSerializer(paginated_logs, many=True)

    return {
        'results': serializer.data,
        'count': total_count,
        'page': page,
        'total_pages': total_pages,
        'page_size': page_size,
    }


def get_reason_summary(user, days=30):
    """Get summary of reasons for missed prayers. Returns dict with reasons map."""
    today = timezone.localdate()
    start_date = today - timedelta(days=days - 1)

    logs = DailyPrayerLog.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=today,
    )

    reason_counts = {}
    prayer_fields = ['fajr_reason', 'dhuhr_reason', 'asr_reason', 'maghrib_reason', 'isha_reason']

    for log in logs:
        for field in prayer_fields:
            reason = getattr(log, field)
            if reason:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

    return {"reasons": reason_counts}


def get_sync_status(user):
    """Get sync status for a user (read-only). Returns dict."""
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


from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from prayers.models import DailyPrayerLog


