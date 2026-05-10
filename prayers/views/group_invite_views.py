from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from prayers.models import Group, GroupMembership
from prayers.selectors.group_selectors import get_group_by_id
from prayers.services.group_service import user_is_group_admin, create_membership, user_can_join_group
from prayers.utils.error_utils import not_found_response, forbidden_response, error_response
from prayers.domain.constants import GroupPrivacy, MembershipStatus, GROUP_MAX_MEMBERS


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_invite_code(request, group_id):
    """
    Generate or retrieve invite code for a group.
    Only group admins can generate invite codes.
    """
    try:
        group = get_group_by_id(group_id)
    except Group.DoesNotExist:
        return not_found_response('Group not found')

    if not user_is_group_admin(request.user, group):
        return forbidden_response('Only group admins can generate invite codes')

    invite_code = group.generate_invite_code()
    return Response({'invite_code': invite_code})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_group(request):
    """
    Join a group using an invite code in the request body.
    Expected: {"invite_code": "NAMAZ-XXXXXX"}
    """
    invite_code = request.data.get('invite_code', '').strip().upper()
    
    if not invite_code:
        return error_response('Invite code required', 'invalid_request', status.HTTP_400_BAD_REQUEST)

    try:
        group = Group.objects.get(invite_code=invite_code)
    except Group.DoesNotExist:
        return not_found_response('Invalid invite code')

    can_join, reason = user_can_join_group(request.user, group)
    if not can_join:
        return forbidden_response(reason)

    # Check if already a member (idempotent join)
    existing = GroupMembership.objects.active().filter(
        user=request.user,
        group=group,
    ).first()

    if existing:
        return Response({
            'group_id': group.id,
            'detail': 'Already a member',
        }, status=status.HTTP_409_CONFLICT)

    try:
        membership = create_membership(request.user, group, 'MEMBER')
    except ValueError as e:
        return forbidden_response(str(e))

    return Response({
        'success': True,
        'group_id': group.id,
        'group_name': group.name,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_group(request):
    """
    Create a new group.
    Expected: {"name": "Group Name"}
    Returns: {"id": group_id, "name": group_name, "invite_code": invite_code}
    """
    name = request.data.get('name', '').strip()

    if not name:
        return error_response('Group name is required', 'MISSING_NAME', status.HTTP_400_BAD_REQUEST)

    if len(name) > 100:
        return error_response('Group name must be 100 characters or less', 'NAME_TOO_LONG', status.HTTP_400_BAD_REQUEST)

    group = Group.objects.create(
        name=name,
        created_by=request.user,
        privacy_level=GroupPrivacy.INVITE_ONLY,
    )

    group.generate_invite_code()

    create_membership(request.user, group, 'ADMIN')

    return Response({
        'id': group.id,
        'name': group.name,
        'invite_code': group.invite_code,
    })