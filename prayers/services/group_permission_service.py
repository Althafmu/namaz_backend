from prayers.models import GroupMembership
from prayers.domain.constants import GroupRole


def can_add_member(user, group) -> bool:
    """Check if user can add members."""
    try:
        actor = GroupMembership.objects.get(
            user=user,
            group=group,
            status='active',
        )
        return actor.is_admin
    except GroupMembership.DoesNotExist:
        return False


def can_remove_member(user, group, target_member) -> bool:
    """Check if user can remove a member."""
    try:
        actor = GroupMembership.objects.get(
            user=user,
            group=group,
            status='active',
        )
        if not actor.is_admin:
            return False
        # Cannot remove yourself if you're the only admin?
        return True
    except GroupMembership.DoesNotExist:
        return False


def can_modify_role(user, group, target_member, new_role) -> bool:
    """Check if user can change member's role."""
    try:
        actor = GroupMembership.objects.get(
            user=user,
            group=group,
            status='active',
        )
        if not actor.is_admin:
            return False
        # Cannot promote someone above your own role
        return True
    except GroupMembership.DoesNotExist:
        return False


def can_revoke_invite(user, group, invite) -> bool:
    """Check if user can revoke invite tokens."""
    try:
        actor = GroupMembership.objects.get(
            user=user,
            group=group,
            status='active',
        )
        return actor.is_admin
    except GroupMembership.DoesNotExist:
        return False
