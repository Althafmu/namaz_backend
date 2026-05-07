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

    # Calculate current user rank if applicable
    if current_user_data:
        user_streak = current_user_data['current_streak']
        rank = sum(1 for m in top_streaks if (m.streak_count or 0) > user_streak) + 1
        current_user_data['rank'] = rank

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

    # Query 5: Recent activity (placeholder for G2.3)
    recent_activity = []

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
