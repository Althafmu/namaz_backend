from prayers.models import Group, GroupMembership, GroupInviteToken
from prayers.domain.constants import GroupRole, GroupPrivacy, GROUP_MAX_MEMBERS, MembershipStatus


def user_is_group_admin(user, group) -> bool:
    """Check if user is an admin of the group."""
    try:
        membership = GroupMembership.objects.active().get(
            user=user,
            group=group,
        )
        return membership.is_admin
    except GroupMembership.DoesNotExist:
        return False


def create_membership(user, group, role=GroupRole.MEMBER) -> GroupMembership:
    """Create a new membership for the user in the group."""
    if GroupMembership.objects.active().filter(user=user, group=group).exists():
        raise ValueError("Already a member of this group")
    
    return GroupMembership.objects.create(
        user=user,
        group=group,
        role=role,
        status=MembershipStatus.ACTIVE,
    )


def user_can_manage_group(user, group) -> bool:
    """Check if user can manage group settings/members."""
    try:
        membership = GroupMembership.objects.active().get(
            user=user,
            group=group,
        )
        return membership.is_admin
    except GroupMembership.DoesNotExist:
        return False


def user_can_view_group(user, group) -> bool:
    """
    TEMPORARY G1 VISIBILITY RULES (Issue #7).
    
    These are simplified rules for G1.
    G2/G3 will introduce fine-grained privacy settings.
    """
    # Public groups: anyone can view
    if group.privacy_level == GroupPrivacy.PUBLIC:
        return True
    
    # Private/Invite-only: must be active member
    return GroupMembership.objects.active().filter(
        user=user,
        group=group,
    ).exists()


def user_can_join_group(user, group, invite_token=None) -> tuple:
    """Returns (allowed: bool, reason: str). Enforces GROUP_MAX_MEMBERS (Issue #8)."""
    # Check if already member
    if GroupMembership.objects.active().filter(
        user=user,
        group=group,
    ).exists():
        return False, "Already a member of this group."
    
    # Check group size limit (Issue #8)
    active_members = group.memberships.active().count()
    if active_members >= GROUP_MAX_MEMBERS:
        return False, f"Group has reached maximum membership limit ({GROUP_MAX_MEMBERS})."
    
    # Check privacy rules
    if group.privacy_level == GroupPrivacy.PUBLIC:
        return True, None
    
    if group.privacy_level == GroupPrivacy.PRIVATE:
        return False, "This group is private. You need an invite."
    
    # INVITE_ONLY: must provide valid token
    if not invite_token:
        return False, "This group requires an invite token to join."
    
    return True, None


def user_can_see_member_prayers(user, group, target_member) -> bool:
    """
    Check if user can see target_member's prayer logs in group.
    
    TEMPORARY G1 RULES (Issue #7):
    - Admins can see all members
    - Members can see other members (subject to target's sharing settings)
    - Viewers cannot see individual logs (viewers don't exist in G1)
    
    Note: Fine-grained privacy settings will be added in G2/G3.
    """
    try:
        viewer_membership = GroupMembership.objects.active().get(
            user=user,
            group=group,
        )
    except GroupMembership.DoesNotExist:
        return False
    
    # Admins can see all
    if viewer_membership.is_admin:
        return True
    
    # Members can see other members (subject to target's sharing settings)
    # For G1, members can see each other's aggregated stats
    return True


def get_group_roles_for_user(user, group) -> list:
    """Get list of roles user can assign (admin only)."""
    try:
        membership = GroupMembership.objects.active().get(
            user=user,
            group=group,
        )
        if membership.is_admin:
            return [GroupRole.ADMIN, GroupRole.MEMBER]
        return []
    except GroupMembership.DoesNotExist:
        return []
