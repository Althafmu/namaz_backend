from django.db import transaction

from prayers.domain.constants import MembershipStatus

# Valid state transitions
# Format: {from_status: [allowed_to_status1, allowed_to_status2, ...]}
VALID_TRANSITIONS = {
    MembershipStatus.ACTIVE: [
        MembershipStatus.LEFT,
        MembershipStatus.REMOVED,
        MembershipStatus.BANNED,
    ],
    MembershipStatus.LEFT: [
        MembershipStatus.ACTIVE,  # Can rejoin
    ],
    MembershipStatus.REMOVED: [
        MembershipStatus.ACTIVE,  # Admin can re-add
    ],
    MembershipStatus.BANNED: [],  # Cannot transition out of banned
}


def can_transition(from_status, to_status) -> bool:
    """
    Check if status transition is allowed.
    Returns True if allowed, False otherwise.
    """
    allowed_transitions = VALID_TRANSITIONS.get(from_status, [])
    return to_status in allowed_transitions


@transaction.atomic
def transition_membership(membership, new_status, changed_by=None):
    """
    Transition membership to new status with validation.
    Raises ValueError if transition is not allowed.
    """
    if membership.status == new_status:
        return membership  # No change needed

    if not can_transition(membership.status, new_status):
        raise ValueError(
            f"Cannot transition membership from {membership.status} to {new_status}"
        )

    old_status = membership.status
    membership.status = new_status
    membership.save(update_fields=['status'])

    # TODO: Log transition for audit trail (future)
    # MembershipAuditLog.objects.create(...)

    return membership


def get_available_transitions(current_status) -> list:
    """
    Get list of available transitions from current status.
    Useful for UI/API to show allowed actions.
    """
    return VALID_TRANSITIONS.get(current_status, [])
