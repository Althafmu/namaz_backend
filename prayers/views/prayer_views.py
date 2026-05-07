from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from drf_spectacular.utils import extend_schema

from prayers.models import DailyPrayerLog
from prayers.serializers import DailyPrayerLogSerializer
from prayers.services.streak_service import attach_recovery_to_logs
from prayers.services.prayer_logging_service import update_today_log, log_prayer
from prayers.services.excused_day_service import set_excused_day, clear_excused_day
from prayers.services.undo_service import undo_last_action
from prayers.selectors import get_today_log, get_prayer_history_queryset, get_detailed_prayer_history, get_reason_summary, get_sync_status
from prayers.utils.api_errors import error_response
from prayers.utils.time_utils import get_effective_today


@extend_schema(tags=["Prayers"])
@api_view(['GET', 'PUT'])
@throttle_classes([ScopedRateThrottle])
def today_prayer_log(request):
    log, created = get_today_log(request.user)
    if log is None:
        if request.method == 'GET':
            return error_response("NOT_FOUND", "No prayer log found for today.", status.HTTP_404_NOT_FOUND)
        # PUT: create/update via service
        try:
            updated_log = update_today_log(
                user=request.user,
                validated_data=request.data,
                target_date=get_effective_today()
            )
            return Response(DailyPrayerLogSerializer(updated_log).data)
        except ValueError as e:
            return error_response("INVALID_INPUT", str(e), status.HTTP_400_BAD_REQUEST)

    if request.method == 'GET':
        attach_recovery_to_logs([log], request.user)
        return Response(DailyPrayerLogSerializer(log).data)

    # PUT
    try:
        updated_log = update_today_log(
            user=request.user,
            validated_data=request.data,
            target_date=log.date
        )
        return Response(DailyPrayerLogSerializer(updated_log).data)
    except ValueError as e:
        return error_response("INVALID_INPUT", str(e), status.HTTP_400_BAD_REQUEST)

today_prayer_log.throttle_scope = "prayer_log"


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

    # Get queryset from selector
    queryset = get_prayer_history_queryset(request.user, days=days)
    total_count = queryset.count()
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    offset = (page - 1) * page_size
    logs_page = queryset[offset:offset + page_size]

    serializer = DailyPrayerLogSerializer(logs_page, many=True)
    return Response({
        'results': serializer.data,
        'count': total_count,
        'page': page,
        'total_pages': total_pages,
        'page_size': page_size,
    })


@extend_schema(tags=["Prayers"])
@api_view(['POST'])
@throttle_classes([ScopedRateThrottle])
def log_single_prayer(request):
    """Delegate to log_prayer with explicit args."""
    try:
        prayer_name = request.data.get('prayer_name')
        if not prayer_name:
            return error_response("MISSING_PRAYER", "prayer_name is required", status.HTTP_400_BAD_REQUEST)
        completed = request.data.get('completed', False)
        status_str = request.data.get('status')
        reason = request.data.get('reason', '')
        target_date_str = request.data.get('date')
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date() if target_date_str else None

        log = log_prayer(
            user=request.user,
            prayer_name=prayer_name,
            completed=completed,
            status=status_str,
            reason=reason,
            target_date=target_date
        )
        return Response(DailyPrayerLogSerializer(log).data)
    except ValueError as e:
        return error_response("INVALID_INPUT", str(e), status.HTTP_400_BAD_REQUEST)

log_single_prayer.throttle_scope = "prayer_log"


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
    days = int(request.query_params.get('days', 30))
    result = get_reason_summary(request.user, days=days)
    return Response(result)


@extend_schema(tags=["Prayers"])
@api_view(['GET'])
def undo_last_prayer_action(request):
    today = get_effective_today()
    try:
        target_date_str = request.query_params.get('date', '')
        if target_date_str:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        else:
            target_date = today - timedelta(days=1)
    except ValueError:
        target_date = today - timedelta(days=1)

    try:
        log = undo_last_action(request.user, target_date)
        if log is None:
            return error_response("NO_ACTION", "No action to undo for this date.", status.HTTP_400_BAD_REQUEST)
        return Response(DailyPrayerLogSerializer(log).data)
    except ValueError as e:
        return error_response("INVALID_INPUT", str(e), status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=["Prayers"])
@api_view(['GET'])
def sync_status_view(request):
    result = get_sync_status(request.user)
    return Response(result)


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
@api_view(['GET'])
def analytics_view(request):
    today = get_effective_today()
    try:
        days = int(request.query_params.get('days', 30))
    except (ValueError, TypeError):
        days = 30

    result = get_detailed_prayer_history(request.user, days=days)
    result.pop('logs', None)
    return Response(result)
