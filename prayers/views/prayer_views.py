from datetime import datetime
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from drf_spectacular.utils import extend_schema

from prayers.models import DailyPrayerLog, Streak
from prayers.serializers import DailyPrayerLogSerializer
from prayers.services.prayer_status_service import classify_prayer_status
from prayers.services.status_service import CanonicalPrayerStatus, canonical_to_db
from prayers.services.streak_service import attach_recovery_to_logs
from prayers.services import prayer_service
from prayers.selectors import get_today_log, get_prayer_history, get_detailed_prayer_history, get_reason_summary, get_sync_status
from prayers.utils.api_errors import error_response
from prayers.utils.time_utils import get_effective_today

from prayers.services.prayer_service import log_prayer, set_excused_day, clear_excused_day


@extend_schema(tags=["Prayers"])
@api_view(['GET', 'PUT'])
@throttle_classes([ScopedRateThrottle])
def today_prayer_log(request):
    log, created = get_today_log(request.user)

    if request.method == 'GET':
        attach_recovery_to_logs([log], request.user)
        serializer = DailyPrayerLogSerializer(log)
        return Response(serializer.data)

    # PUT - update today's log via service
    try:
        updated_log = prayer_service.update_today_log(
            user=request.user,
            data=request.data,
            target_date=log.date,
        )
        return Response(DailyPrayerLogSerializer(updated_log).data)
    except ValueError as e:
        return error_response("INVALID_INPUT", str(e), status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=["Prayers"])
@api_view(['GET'])
def prayer_history(request):
    try:
        days = int(request.query_params.get('days', 7))
    except (ValueError, TypeError):
        return error_response("INVALID_DAYS", "days parameter must be a valid integer", status.HTTP_400_BAD_REQUEST)

    if days < 1 or days > 365:
        return error_response("INVALID_DAYS_RANGE", "days parameter must be between 1 and 365", status.HTTP_400_BAD_REQUEST)

    try:
        page = int(request.query_params.get('page', 1))
    except (ValueError, TypeError):
        page = 1

    page_size = 30
    page = max(1, page)

    result = get_prayer_history(request.user, days=days, page=page, page_size=page_size)
    logs_page = result['results']
    serializer = DailyPrayerLogSerializer(logs_page, many=True)
    return Response({
        'results': serializer.data,
        'count': result['count'],
        'page': result['page'],
        'total_pages': result['total_pages'],
        'page_size': result['page_size'],
    })


@extend_schema(tags=["Prayers"])
@api_view(['POST'])
@throttle_classes([ScopedRateThrottle])
def log_single_prayer(request):
    """Delegate to prayer_service.log_prayer."""
    try:
        log = prayer_service.log_prayer(request.user, request.data)
        return Response(DailyPrayerLogSerializer(log).data)
    except ValueError as e:
        return error_response("INVALID_INPUT", str(e), status.HTTP_400_BAD_REQUEST)

log_single_prayer.throttle_scope = "prayer_log"


@extend_schema(tags=["Prayers"])
@api_view(['GET'])
def detailed_prayer_history(request):
    today = get_effective_today()
    try:
        year = int(request.query_params.get('year', today.year))
    except (ValueError, TypeError):
        return error_response("INVALID_YEAR", "year parameter must be a valid integer", status.HTTP_400_BAD_REQUEST)

    result = get_detailed_prayer_history(request.user, year=year)
    return Response(result)


@extend_schema(tags=["Prayers"])
@api_view(['POST', 'DELETE'])
def set_excused_day(request):
    try:
        target_date = datetime.strptime(request.data.get('date', ''), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        target_date = get_effective_today()

    log = set_excused_day(request.user, target_date)
    if log is None:
        return error_response("NOT_FOUND", "No prayer log found for this date.", status.HTTP_404_NOT_FOUND)
    return Response(DailyPrayerLogSerializer(log).data)


@extend_schema(tags=["Prayers"])
@api_view(['POST', 'DELETE'])
def clear_excused_day(request):
    try:
        target_date = datetime.strptime(request.data.get('date', ''), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        target_date = get_effective_today()

    log = clear_excused_day(request.user, target_date)
    if log is None:
        return error_response("NOT_FOUND", "No prayer log found for this date.", status.HTTP_404_NOT_FOUND)
    return Response(DailyPrayerLogSerializer(log).data)


@extend_schema(tags=["Prayers"])
@api_view(['GET'])
def reason_summary(request):
    today = get_effective_today()
    days = int(request.query_params.get('days', 30))
    result = get_reason_summary(request.user, days=days)
    return Response(result)


@extend_schema(tags=["Prayers"])
@api_view(['GET'])
def undo_last_prayer_action(request):
    today = get_effective_today()
    try:
        target_date = datetime.strptime(request.data.get('date', ''), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        target_date = today - timezone.timedelta(days=1)

    # Service handles the undo logic
    try:
        log = prayer_service.undo_last_action(request.user, target_date)
        if log is None:
            return error_response("NO_ACTION", "No action to undo for this date.", status.HTTP_400_BAD_REQUEST)
        return Response(DailyPrayerLogSerializer(log).data)
    except ValueError as e:
        return error_response("INVALID_INPUT", str(e), status.HTTP_400_BAD_REQUEST)


undo_last_prayer_action.throttle_scope = "prayer_log"


@extend_schema(tags=["Prayers"])
@api_view(['GET'])
def sync_status_view(request):
    result = get_sync_status(request.user)
    return Response(result)


@extend_schema(tags=["Prayers"])
@api_view(['GET'])
def analytics_view(request):
    today = get_effective_today()
    try:
        days = int(request.query_params.get('days', 30))
    except (ValueError, TypeError):
        days = 30

    result = get_detailed_prayer_history(request.user, days=days)
    result.pop('logs', None)  # Remove logs, keep stats
    return Response(result)
