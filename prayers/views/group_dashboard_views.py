from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from prayers.models import Group
from prayers.selectors.group_dashboard_selector import get_group_dashboard
from prayers.serializers.group_dashboard_serializers import DashboardSerializer
from prayers.services.group_service import user_can_view_group
from prayers.domain.constants import GroupPrivacy


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([AllowAny])
def group_dashboard_view(request, group_id):
    """
    Dashboard endpoint for group home screen.
    Returns aggregated data in single payload.
    Target: ≤6 queries.
    """
    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

    # Check permission - allow unauthenticated for public groups
    if group.privacy_level != GroupPrivacy.PUBLIC and not request.user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    if not user_can_view_group(request.user, group):
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)

    # Get dashboard data via selector
    data = get_group_dashboard(group, request.user if request.user.is_authenticated else None)
    if data is None:
        return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

    # Serialize and return
    serializer = DashboardSerializer(data)
    return Response(serializer.data)
