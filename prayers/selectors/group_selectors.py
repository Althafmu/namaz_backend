from django.db.models import Count, Q, Exists, OuterRef

from prayers.models import Group, GroupMembership
from prayers.domain.constants import MembershipStatus


def get_group_queryset(user=None, privacy_filter=None):
    """Return QuerySet of groups. No pagination/evaluation."""
    qs = Group.objects.all()
    
    if privacy_filter:
        qs = qs.filter(privacy_level=privacy_filter)
    
    # Annotate member counts (Issue 6: avoid N+1)
    qs = qs.annotate(
        member_count=Count('memberships', filter=Q(memberships__status=MembershipStatus.ACTIVE))
    )
    
    # Annotate user membership using Exists (boolean semantics) - Task 3
    if user:
        qs = qs.annotate(
            user_is_member=Exists(
                GroupMembership.objects.filter(
                    group=OuterRef('pk'),
                    user=user,
                    status=MembershipStatus.ACTIVE
                )
            )
        )
    
    return qs.order_by('-created_at')


def get_user_groups_queryset(user):
    """Return QuerySet of groups user belongs to."""
    return Group.objects.filter(
        memberships__user=user,
        memberships__status=MembershipStatus.ACTIVE,
    ).annotate(
        member_count=Count('memberships', filter=Q(memberships__status=MembershipStatus.ACTIVE))
    ).order_by('-created_at')


def get_group_by_id(group_id):
    """Get group by ID. Returns Group object or raises DoesNotExist."""
    return Group.objects.get(id=group_id)

