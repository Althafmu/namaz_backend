from datetime import datetime

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from prayers.models import DailyPrayerLog, Streak
from prayers.serializers import DailyPrayerLogSerializer
from prayers.services.prayer_status_service import classify_prayer_status
from prayers.services.status_service import CanonicalPrayerStatus, canonical_to_db
from prayers.services.streak_service import attach_recovery_to_logs
from prayers.utils.api_errors import error_response
from prayers.utils.time_utils import get_effective_today


def _parse_logged_at(request):
    logged_at = request.data.get("logged_at")
    if not logged_at:
        return timezone.now()
    if isinstance(logged_at, str):
        try:
            dt = datetime.fromisoformat(logged_at)
            return dt if timezone.is_aware(dt) else timezone.make_aware(dt)
        except ValueError:
            raise ValueError("Invalid logged_at format. Expected ISO datetime.")
    raise ValueError("logged_at must be an ISO datetime string.")


def _resolve_status(prayer_name, completed, request):
    if not completed:
        return canonical_to_db(CanonicalPrayerStatus.MISSED)

    prayer_time_windows = request.data.get("prayer_time_windows")
    logged_at = _parse_logged_at(request)
    if prayer_time_windows:
        canonical_status = classify_prayer_status(
            prayer_name=prayer_name,
            logged_at=logged_at,
            prayer_time_windows=prayer_time_windows,
            config=request.data.get("config") or {},
        )
        return canonical_to_db(canonical_status)

    # Compatibility fallback: keep accepting explicit status during transition
    explicit_status = request.data.get('status')
    if isinstance(explicit_status, str):
        status_lower = explicit_status.strip().lower()
        if status_lower in {'on_time', 'late', 'qada', 'missed'}:
            return status_lower
        if status_lower in {'excused', 'pending'}:
            return status_lower
        raise ValueError("Invalid status. Must be one of: ['on_time', 'late', 'missed', 'qada', 'excused', 'pending']")
    return canonical_to_db(CanonicalPrayerStatus.ONTIME)


@api_view(['GET', 'PUT'])
def today_prayer_log(request):
    today = get_effective_today()
    log, _ = DailyPrayerLog.objects.get_or_create(user=request.user, date=today)

    if request.method == 'GET':
        attach_recovery_to_logs([log], request.user)
        serializer = DailyPrayerLogSerializer(log)
        return Response(serializer.data)

    serializer = DailyPrayerLogSerializer(log, data=request.data, partial=True)
    if serializer.is_valid():
        updated_log = serializer.save()
        streak, _ = Streak.objects.get_or_create(user=request.user)
        streak.recalculate(force=False, changed_date=today)
        attach_recovery_to_logs([updated_log], request.user)
        return Response(DailyPrayerLogSerializer(updated_log).data)
    return error_response("VALIDATION_ERROR", "Invalid request body.", status.HTTP_400_BAD_REQUEST, field_errors=serializer.errors)


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

    today = get_effective_today()
    start_date = today - timezone.timedelta(days=days - 1)
    logs = DailyPrayerLog.objects.filter(user=request.user, date__gte=start_date, date__lte=today).order_by('date')

    total_count = logs.count()
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    offset = (page - 1) * page_size
    logs_page = logs[offset:offset + page_size]

    serializer = DailyPrayerLogSerializer(logs_page, many=True)
    return Response({
        'results': serializer.data,
        'count': total_count,
        'page': page,
        'total_pages': total_pages,
        'page_size': page_size,
    })


@api_view(['POST'])
@throttle_classes([ScopedRateThrottle])
def log_single_prayer(request):
    prayer_name = request.data.get('prayer', '').lower()
    completed = request.data.get('completed', True)
    in_jamaat = request.data.get('in_jamaat', False)
    location = request.data.get('location', 'home')
    reason = request.data.get('reason', None)
    date_str = request.data.get('date', None)
    prayed_jumah = request.data.get('prayed_jumah', False)

    valid_prayers = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']
    if prayer_name not in valid_prayers:
        return error_response("INVALID_PRAYER_NAME", f'Invalid prayer name. Must be one of: {valid_prayers}', status.HTTP_400_BAD_REQUEST)

    if reason:
        reason = str(reason).strip()[:255]

    today = get_effective_today()
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return error_response("INVALID_DATE_FORMAT", "Invalid date format. Expected YYYY-MM-DD.", status.HTTP_400_BAD_REQUEST)

        days_ago = (today - target_date).days
        if days_ago < 0:
            return error_response("FUTURE_DATE_NOT_ALLOWED", "Cannot log prayers for future dates.", status.HTTP_400_BAD_REQUEST)
        if days_ago > 2:
            return error_response("EDIT_WINDOW_EXCEEDED", "Cannot edit prayers more than 2 days in the past.", status.HTTP_400_BAD_REQUEST)
    else:
        target_date = today

    try:
        prayer_status = _resolve_status(prayer_name, completed, request)
    except ValueError as exc:
        return error_response("INVALID_STATUS_CLASSIFICATION_INPUT", str(exc), status.HTTP_400_BAD_REQUEST)

    log, _ = DailyPrayerLog.objects.get_or_create(user=request.user, date=target_date)
    prayer_field_map = {
        'fajr': ('fajr', 'fajr_in_jamaat', 'fajr_status', 'fajr_reason'),
        'dhuhr': ('dhuhr', 'dhuhr_in_jamaat', 'dhuhr_status', 'dhuhr_reason'),
        'asr': ('asr', 'asr_in_jamaat', 'asr_status', 'asr_reason'),
        'maghrib': ('maghrib', 'maghrib_in_jamaat', 'maghrib_status', 'maghrib_reason'),
        'isha': ('isha', 'isha_in_jamaat', 'isha_status', 'isha_reason'),
    }
    fields = prayer_field_map[prayer_name]
    setattr(log, fields[0], completed)
    setattr(log, fields[1], in_jamaat)
    setattr(log, fields[2], prayer_status)
    setattr(log, fields[3], reason)
    log.location = location

    if prayer_name == 'dhuhr':
        log.prayed_jumah = prayed_jumah

    try:
        log.full_clean()
    except DjangoValidationError as e:
        return error_response("VALIDATION_ERROR", f'Validation error: {e.message_dict}', status.HTTP_400_BAD_REQUEST)

    log.save()

    streak, _ = Streak.objects.get_or_create(user=request.user)
    streak.recalculate(force=False, changed_date=target_date)

    attach_recovery_to_logs([log], request.user)
    serializer = DailyPrayerLogSerializer(log)
    return Response(serializer.data)


log_single_prayer.throttle_scope = "prayer_log"


@api_view(['GET'])
def detailed_prayer_history(request):
    today = get_effective_today()
    try:
        year = int(request.query_params.get('year', today.year))
    except (ValueError, TypeError):
        return error_response("INVALID_YEAR", "year parameter must be a valid integer", status.HTTP_400_BAD_REQUEST)

    try:
        month = int(request.query_params.get('month', today.month))
    except (ValueError, TypeError):
        return error_response("INVALID_MONTH", "month parameter must be a valid integer", status.HTTP_400_BAD_REQUEST)

    if month < 1 or month > 12:
        return error_response("INVALID_MONTH_RANGE", "month must be between 1 and 12", status.HTTP_400_BAD_REQUEST)

    try:
        page = int(request.query_params.get('page', 1))
    except (ValueError, TypeError):
        page = 1

    page_size = 15
    page = max(1, page)
    logs = DailyPrayerLog.objects.filter(user=request.user, date__year=year, date__month=month).order_by('date')
    total_count = logs.count()
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    offset = (page - 1) * page_size
    logs_page = logs[offset:offset + page_size]
    serializer = DailyPrayerLogSerializer(logs_page, many=True)
    return Response({
        'results': serializer.data,
        'count': total_count,
        'page': page,
        'total_pages': total_pages,
        'page_size': page_size,
    })


@api_view(['GET'])
def reason_summary(request):
    from django.db.models import Count

    prayer_names = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']
    reason_counts = {}
    for prayer in prayer_names:
        status_field = f'{prayer}_status'
        reason_field = f'{prayer}_reason'
        reasons = (
            DailyPrayerLog.objects.filter(user=request.user)
            .filter(**{f'{status_field}__in': ['late', 'missed']})
            .exclude(**{f'{reason_field}__isnull': True})
            .exclude(**{f'{reason_field}': ''})
            .values(reason_field)
            .annotate(count=Count(reason_field))
        )
        for item in reasons:
            reason = item[reason_field]
            if reason:
                reason_counts[reason] = reason_counts.get(reason, 0) + item['count']
    return Response({'reasons': reason_counts})


@api_view(['POST'])
def set_excused_day(request):
    date_str = request.data.get('date')
    reason = request.data.get('reason', 'excused')
    prayer_names = request.data.get('prayer_names')  # Optional: specific prayers to excuse
    if not date_str:
        return error_response("MISSING_DATE", "date is required. Format: YYYY-MM-DD", status.HTTP_400_BAD_REQUEST)
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return error_response("INVALID_DATE_FORMAT", "Invalid date format. Expected YYYY-MM-DD.", status.HTTP_400_BAD_REQUEST)

    today = get_effective_today()
    days_ago = (today - target_date).days
    if days_ago < -7:
        return error_response("EXCUSED_FUTURE_LIMIT", "Cannot set excused more than 7 days in the future.", status.HTTP_400_BAD_REQUEST)
    if days_ago > 30:
        return error_response("EXCUSED_PAST_LIMIT", "Cannot set excused more than 30 days in the past.", status.HTTP_400_BAD_REQUEST)

    log, _ = DailyPrayerLog.objects.get_or_create(user=request.user, date=target_date)
    excused_reason = reason[:255] if reason else 'excused'

    # If specific prayers are provided, only excuse those; otherwise excuse all pending
    if prayer_names and isinstance(prayer_names, list):
        target_prayers = [p for p in prayer_names if p in ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']]
    else:
        target_prayers = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']

    # Only mark prayers that haven't been actively logged yet.
    # This preserves any prayers the user already recorded before
    # entering excused mode (e.g., logged Fajr/Dhuhr, then started travelling).
    for prayer in target_prayers:
        current_status = getattr(log, f'{prayer}_status')
        if current_status in ('pending', None, ''):
            setattr(log, prayer, True)
            setattr(log, f'{prayer}_status', 'excused')
            setattr(log, f'{prayer}_reason', excused_reason)

    log.save()

    streak, _ = Streak.objects.get_or_create(user=request.user)
    streak.recalculate(force=False, changed_date=target_date)
    return Response(DailyPrayerLogSerializer(log).data)


@api_view(['POST'])
def clear_excused_day(request):
    date_str = request.data.get('date')
    if not date_str:
        return error_response("MISSING_DATE", "date is required. Format: YYYY-MM-DD", status.HTTP_400_BAD_REQUEST)

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return error_response("INVALID_DATE_FORMAT", "Invalid date format. Expected YYYY-MM-DD.", status.HTTP_400_BAD_REQUEST)

    try:
        log = DailyPrayerLog.objects.get(user=request.user, date=target_date)
    except DailyPrayerLog.DoesNotExist:
        log, _ = DailyPrayerLog.objects.get_or_create(user=request.user, date=target_date)

    for prayer in ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']:
        status_field = f'{prayer}_status'
        reason_field = f'{prayer}_reason'
        in_jamaat_field = f'{prayer}_in_jamaat'

        if getattr(log, status_field) == 'excused':
            setattr(log, prayer, False)
            setattr(log, status_field, 'pending')
            setattr(log, reason_field, None)
            setattr(log, in_jamaat_field, False)

    log.save()

    streak, _ = Streak.objects.get_or_create(user=request.user)
    streak.recalculate(force=False, changed_date=target_date)
    attach_recovery_to_logs([log], request.user)
    return Response(DailyPrayerLogSerializer(log).data)


@api_view(['GET'])
def analytics_view(request):
    today = get_effective_today()
    start_date = today - timezone.timedelta(days=6)
    logs = DailyPrayerLog.objects.filter(user=request.user, date__gte=start_date, date__lte=today)
    counts = {'fajr': 0, 'dhuhr': 0, 'asr': 0, 'maghrib': 0, 'isha': 0, 'on_time': 0, 'late': 0, 'missed': 0, 'qada': 0}
    total_valid = 0
    excused_count = 0
    for log in logs:
        for prayer in ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']:
            current_prayer_status = getattr(log, f'{prayer}_status')
            completed = getattr(log, prayer)
            if current_prayer_status == 'excused':
                counts[prayer] += 1
                excused_count += 1
                total_valid += 1
            elif completed:
                counts[prayer] += 1
                total_valid += 1
                if current_prayer_status in counts:
                    counts[current_prayer_status] += 1
    return Response({**counts, 'total_valid': total_valid, 'excused_count': excused_count})


def _infer_undo_prayer_name(log):
    """Best-effort fallback for legacy undo calls without prayer/date payload."""
    # Reverse chronological prayer order for a typical day.
    for prayer in ['isha', 'maghrib', 'asr', 'dhuhr', 'fajr']:
        if getattr(log, prayer):
            return prayer
    return None


@api_view(['POST'])
def undo_last_prayer_action(request):
    prayer_name = str(request.data.get('prayer', '')).strip().lower()
    date_str = request.data.get('date')
    valid_prayers = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']

    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return error_response("INVALID_DATE_FORMAT", "Invalid date format. Expected YYYY-MM-DD.", status.HTTP_400_BAD_REQUEST)
    else:
        # Legacy fallback: default to today when date is omitted.
        target_date = get_effective_today()

    try:
        log = DailyPrayerLog.objects.get(user=request.user, date=target_date)
    except DailyPrayerLog.DoesNotExist:
        return error_response("LOG_NOT_FOUND", f"No prayer log found for {target_date}.", status.HTTP_404_NOT_FOUND)

    if prayer_name:
        if prayer_name not in valid_prayers:
            return error_response("INVALID_PRAYER_NAME", f'Invalid prayer name. Must be one of: {valid_prayers}', status.HTTP_400_BAD_REQUEST)
    else:
        # Legacy fallback: infer the latest completed prayer for the selected date.
        prayer_name = _infer_undo_prayer_name(log)
        if prayer_name is None:
            return error_response(
                "UNDO_NOT_AVAILABLE",
                "No completed prayer found to undo for the selected date.",
                status.HTTP_400_BAD_REQUEST,
            )

    if not getattr(log, prayer_name):
        return error_response(
            "UNDO_NOT_AVAILABLE",
            f"{prayer_name.title()} is not marked as completed for {target_date}.",
            status.HTTP_400_BAD_REQUEST,
        )

    setattr(log, prayer_name, False)
    setattr(log, f"{prayer_name}_in_jamaat", False)
    setattr(log, f"{prayer_name}_status", "pending")
    setattr(log, f"{prayer_name}_reason", None)
    if prayer_name == 'dhuhr':
        log.prayed_jumah = False
    log.save()

    streak, _ = Streak.objects.get_or_create(user=request.user)
    streak.recalculate(force=False, changed_date=target_date)
    return Response(DailyPrayerLogSerializer(log).data)


@api_view(['GET'])
def sync_status_view(request):
    pending_count = 0
    for prayer in ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']:
        pending_count += DailyPrayerLog.objects.filter(user=request.user, **{f"{prayer}_status": "pending"}).count()
    return Response({"pending_count": pending_count})
