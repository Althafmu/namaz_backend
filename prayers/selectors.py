from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count, Case, When, IntegerField, F
from prayers.models import DailyPrayerLog, Streak


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
    start_date = today - timezone.timedelta(days=days - 1)
    
    return DailyPrayerLog.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=today,
    ).order_by('-date')
    # Returns QuerySet - caller decides pagination


def get_detailed_prayer_history(user, days=30):
    """Get detailed prayer history statistics (read-only). Returns dict with QuerySet."""
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
        'logs': logs,  # QuerySet, not evaluated
        'total_days': total_days,
        'completed_days': completed_days,
        'completion_rate': (completed_days / total_days * 100) if total_days > 0 else 0,
    }


def get_reason_summary(user, days=30):
    """Get summary of reasons for missed prayers (read-only). Returns QuerySet."""
    today = timezone.localdate()
    start_date = today - timezone.timedelta(days=days - 1)
    
    logs = DailyPrayerLog.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=today,
    )
    
    # Aggregate reasons - returns QuerySet (not evaluated)
    return logs.values('fajr_reason', 'dhuhr_reason', 'asr_reason', 'maghrib_reason', 'isha_reason').annotate(
        count=Count('id')
    )


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


from django.db.models import Count
from prayers.models import Group, GroupMembership


def get_group_queryset(user=None, privacy_filter=None):
    """Return QuerySet of groups. No pagination/evaluation."""
    qs = Group.objects.all()
    
    if privacy_filter:
        qs = qs.filter(privacy_level=privacy_filter)
    
    # Annotate member counts (Issue 6: avoid N+1)
    qs = qs.annotate(
        member_count=Count('memberships', filter=Q(memberships__is_active=True))
    )
    
    # Annotate user membership if user provided (Fix #16)
    if user:
        qs = qs.annotate(
            user_is_member=Count(
                'memberships',
                filter=Q(memberships__user=user, memberships__is_active=True)
            )
        )
    
    return qs.order_by('-created_at')


def get_user_groups_queryset(user):
    """Return QuerySet of groups user belongs to."""
    return Group.objects.filter(
        memberships__user=user,
        memberships__is_active=True,
    ).annotate(
        member_count=Count('memberships', filter=Q(memberships__is_active=True))
    ).order_by('-created_at')
