import hashlib
from django.db import transaction
from django.utils.crypto import get_random_string
from prayers.models import GroupInviteToken, GroupMembership
from prayers.domain.constants import GroupRole, MembershipStatus


@transaction.atomic
def create_group_invite(group, created_by, max_uses=1, days_valid=7):
    """Create invite (returns RAW token, stores hash). Moved from model (Issue #2, #3)."""
    raw_token = get_random_string(64)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    
    invite = GroupInviteToken.objects.create(
        group=group,
        created_by=created_by,
        token_hash=token_hash,
        max_uses=max_uses,
        expires_at=timezone.now() + timedelta(days=days_valid),
    )
    return raw_token


@transaction.atomic
def consume_invite_token(token_str, user):
    """Race-condition safe token consumption. Moved from model (Issue #2, #3)."""
    token_hash = hashlib.sha256(token_str.encode()).hexdigest()
    
    # Use select_for_update() for race condition safety
    try:
        invite = GroupInviteToken.objects.select_for_update().get(
            token_hash=token_hash,
            is_revoked=False,
        )
    except GroupInviteToken.DoesNotExist:
        return None, "Invalid or expired invite token."
    
    if not invite.is_valid():
        invite.is_revoked = True
        invite.save(update_fields=['is_revoked'])
        return None, "Invalid or expired invite token."
    
    # Check if user already member
    membership, created = GroupMembership.objects.get_or_create(
        user=user,
        group=invite.group,
        defaults={'role': GroupRole.MEMBER},
    )
    
    if not created and membership.status != MembershipStatus.ACTIVE:
        membership.status = MembershipStatus.ACTIVE
        membership.save(update_fields=['status'])
    
    invite.uses_count += 1
    if invite.uses_count >= invite.max_uses:
        invite.is_revoked = True
    invite.save(update_fields=['uses_count', 'is_revoked'])
    
    return membership, None
