from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from prayers.models import Group
from prayers.selectors.group_selectors import get_group_by_id
from prayers.services.group_service import user_is_group_admin, create_membership
from prayers.utils.error_utils import not_found_response, forbidden_response, error_response
from prayers.domain.constants import GroupPrivacy


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

    if group.privacy_level == GroupPrivacy.PRIVATE:
        return forbidden_response('This group requires approval. Contact the group admin.')

    try:
        membership = create_membership(request.user, group, 'MEMBER')
    except ValueError as e:
        return forbidden_response(str(e))

    return Response({
        'success': True,
        'group_id': group.id,
        'group_name': group.name,
    })