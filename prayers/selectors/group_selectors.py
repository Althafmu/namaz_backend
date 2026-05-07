from django.db.models import Count, Q

from prayers.models import Group


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

