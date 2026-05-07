from datetime import timedelta

from django.db.models import Count, Q, F
from django.utils import timezone

from prayers.models import Group, GroupMembership, DailyPrayerLog
from prayers.domain.constants import MembershipStatus


def get_group_dashboard(group, user):
    """
    Single optimized query aggregation for group dashboard.
    Returns dict with all dashboard data.
    Target: ≤6 queries.
    """
    # Query 1: Group metadata + member_count
    group_qs = Group.objects.filter(id=group.id).annotate(
        member_count=Count(
            'memberships',
            filter=Q(memberships__status=MembershipStatus.ACTIVE)
        )
    ).select_related('created_by')

    group_data = group_qs.first()
    if not group_data:
        return None

    # Query 2: Current user membership + streak
    current_user_data = None
    if user and user.is_authenticated:
        membership = GroupMembership.objects.filter(
            user=user,
            group=group,
            status=MembershipStatus.ACTIVE
        ).select_related('user__streak').first()

        if membership:
            streak = getattr(membership.user, 'streak', None)
            current_user_data = {
                'role': membership.role,
                'joined_at': membership.joined_at,
                'current_streak': streak.current_streak if streak else 0,
                'rank': None  # Calculated below
            }

    # Query 3: Top 5 streaks (leaderboard preview)
    top_streaks = GroupMembership.objects.filter(
        group=group,
        status=MembershipStatus.ACTIVE
    ).select_related('user', 'user__streak').annotate(
        streak_count=F('user__streak__current_streak')
    ).order_by('-streak_count')[:5]

    leaderboard = [
        {
            'username': m.user.username,
            'streak': m.streak_count or 0,
            'rank': idx + 1
        }
        for idx, m in enumerate(top_streaks)
    ]

    # Calculate current user rank across ALL active members
    if current_user_data:
        user_streak = current_user_data['current_streak']
        # Count all active members with higher streaks
        higher_count = GroupMembership.objects.filter(
            group=group,
            status=MembershipStatus.ACTIVE,
            user__streak__current_streak__gt=user_streak
        ).count()
        current_user_data['rank'] = higher_count + 1

    # Query 4: Today's prayer completion stats
    today = timezone.localdate()

    today_stats = DailyPrayerLog.objects.filter(
        user__group_memberships__group=group,
        user__group_memberships__status=MembershipStatus.ACTIVE,
        date=today
    ).aggregate(
        fajr_completed=Count('id', filter=Q(fajr=True)),
        dhuhr_completed=Count('id', filter=Q(dhuhr=True)),
        asr_completed=Count('id', filter=Q(asr=True)),
        maghrib_completed=Count('id', filter=Q(maghrib=True)),
        isha_completed=Count('id', filter=Q(isha=True)),
    )

    today_completion = {
        'fajr': today_stats['fajr_completed'] or 0,
        'dhuhr': today_stats['dhuhr_completed'] or 0,
        'asr': today_stats['asr_completed'] or 0,
        'maghrib': today_stats['maghrib_completed'] or 0,
        'isha': today_stats['isha_completed'] or 0,
    }

    # Query 5: Recent activity (G2.3)
    recent_activity = get_group_activities(group)

    return {
        'group': {
            'id': group_data.id,
            'name': group_data.name,
            'description': group_data.description,
            'privacy_level': group_data.privacy_level,
            'member_count': group_data.member_count,
            'created_by': group_data.created_by.username,
        },
        'current_user': current_user_data,
        'stats': {
            'weekly_completion': 0  # Placeholder for G2.7 analytics
        },
        'top_streaks': leaderboard,
        'recent_activity': recent_activity,
        'today_completion': today_completion,
    }


def get_group_activities(group, limit=20):
    """
    Collect recent group activities from multiple sources.
    Target: ≤3 queries.
    """
    activities = []
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    # Query 1: Recent joins (last 30 days)
    recent_joins = GroupMembership.objects.filter(
        group=group,
        status=MembershipStatus.ACTIVE,
        joined_at__gte=thirty_days_ago
    ).select_related('user').order_by('-joined_at')[:10]

    for m in recent_joins:
        if m.user and m.user.username:
            activities.append({
                'type': 'join',
                'username': m.user.username,
                'created_at': m.joined_at if m.joined_at else now,
                'message': f'{m.user.username} joined the group'
            })

    # Query 2: Recent streak achievements (active members with significant streaks)
    high_streaks = GroupMembership.objects.filter(
        group=group,
        status=MembershipStatus.ACTIVE,
    ).select_related('user__streak').filter(
        user__streak__current_streak__gte=7
    ).order_by('-user__streak__current_streak')[:10]

    for m in high_streaks:
        streak = getattr(m.user, 'streak', None)
        if streak and streak.current_streak >= 7 and m.user and m.user.username:
            activities.append({
                'type': 'streak_milestone',
                'username': m.user.username,
                'created_at': streak.last_recalculated_at if streak.last_recalculated_at else now,
                'message': f'{m.user.username} has {streak.current_streak} day streak 🔥'
            })

    # Query 3: Perfect day completions (last 7 days)
    today = timezone.localdate()
    perfect_days = DailyPrayerLog.objects.filter(
        user__group_memberships__group=group,
        user__group_memberships__status=MembershipStatus.ACTIVE,
        date__gte=today - timedelta(days=7),
        fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True
    ).select_related('user').order_by('-date')[:10]

    for log in perfect_days:
        if log.user and log.user.username:
            activities.append({
                'type': 'completion',
                'username': log.user.username,
                'created_at': log.created_at if log.created_at else now,
                'message': f'{log.user.username} completed all 5 prayers'
            })

    # Sort by created_at descending, return top `limit`
    activities.sort(key=lambda x: x['created_at'], reverse=True)
    return activities[:limit]
