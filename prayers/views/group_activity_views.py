from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from prayers.selectors.group_selectors import get_group_by_id
from prayers.selectors.group_dashboard_selector import get_group_activities
from prayers.serializers.group_dashboard_serializers import ActivitySerializer
from prayers.services.group_service import user_can_view_group
from prayers.domain.constants import GroupPrivacy


@api_view(['GET'])
@permission_classes([AllowAny])
def group_activity_view(request, group_id):
    """
    Activity feed endpoint for group.
    Returns recent activities (joins, milestones, completions).
    """
    try:
        group = get_group_by_id(group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

    if group.privacy_level != GroupPrivacy.PUBLIC and not request.user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    if not user_can_view_group(request.user, group):
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)

    activities = get_group_activities(group, limit=20)
    serializer = ActivitySerializer(activities, many=True)
    return Response(serializer.data)