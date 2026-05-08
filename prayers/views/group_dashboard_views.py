from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from prayers.models import Group
from prayers.selectors.group_selectors import get_group_by_id
from prayers.selectors.group_dashboard_selector import get_group_dashboard
from prayers.serializers.group_dashboard_serializers import DashboardSerializer
from prayers.services.group_service import user_can_view_group
from prayers.domain.constants import GroupPrivacy
from prayers.utils.error_utils import not_found_response, unauthorized_response, forbidden_response


@api_view(['GET'])
@permission_classes([AllowAny])
def group_dashboard_view(request, group_id):
    """
    Dashboard endpoint for group home screen.
    Returns aggregated data in single payload.
    Target: ≤6 queries.
    """
    try:
        group = get_group_by_id(group_id)
    except Group.DoesNotExist:
        return not_found_response('Group not found')

    # Check permission - allow unauthenticated for public groups
    if group.privacy_level != GroupPrivacy.PUBLIC and not request.user.is_authenticated:
        return unauthorized_response()

    if not user_can_view_group(request.user, group):
        return forbidden_response()

    # Get dashboard data via selector
    data = get_group_dashboard(group, request.user if request.user.is_authenticated else None)
    if data is None:
        return not_found_response()

    # Serialize and return
    serializer = DashboardSerializer(data)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_groups_view(request):
    """
    Return list of groups the authenticated user belongs to.
    """
    from rest_framework.permissions import IsAuthenticated
    from prayers.selectors.group_selectors import get_user_groups_queryset

    groups = get_user_groups_queryset(request.user).values(
        'id', 'name', 'privacy_level', 'member_count'
    )

    memberships = request.user.group_memberships.filter(
        status='active'
    ).values('group_id', 'role')
    role_map = {m['group_id']: m['role'] for m in memberships}

    result = []
    for group in groups:
        result.append({
            'id': group['id'],
            'name': group['name'],
            'privacy_level': group['privacy_level'],
            'member_count': group['member_count'],
            'user_role': role_map.get(group['id'], 'member'),
        })

    return Response(result)