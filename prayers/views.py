from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import DailyPrayerLog, Streak, UserSettings
from .serializers import RegisterSerializer, DailyPrayerLogSerializer, StreakSerializer, UserProfileSerializer, UserSettingsSerializer

def get_effective_today():
    """
    Returns the effective date for prayer logging.
    Uses midnight rollover to match frontend behavior.
    """
    return timezone.localtime().date()


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — Create a new user account."""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PUT /api/auth/profile/ — View/update authenticated user's profile."""
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


@api_view(['PATCH'])
@permission_classes([permissions.IsAuthenticated])
def profile_offsets_view(request):
    """
    PATCH /api/profile/offsets/ — Update calculation settings (manual_offsets, method, hanafi).
    EPIC 3: Cloud Sync for manual prayer time offsets.
    """
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)

    manual_offsets = request.data.get('manual_offsets')
    calculation_method = request.data.get('calculation_method')
    use_hanafi = request.data.get('use_hanafi')

    if manual_offsets is not None:
        if not isinstance(manual_offsets, dict):
            return Response(
                {'error': 'manual_offsets must be a JSON object'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Validate offset keys and values
        valid_keys = {'Fajr', 'Sunrise', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'}
        for key, value in manual_offsets.items():
            if key not in valid_keys:
                return Response(
                    {'error': f'Invalid offset key: {key}. Must be one of {valid_keys}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not isinstance(value, int):
                return Response(
                    {'error': f'Offset value for {key} must be an integer'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        settings_obj.manual_offsets = manual_offsets

    if calculation_method is not None:
        settings_obj.calculation_method = str(calculation_method)[:20]

    if use_hanafi is not None:
        settings_obj.use_hanafi = bool(use_hanafi)

    settings_obj.save()
    return Response(UserSettingsSerializer(settings_obj).data)


class DeleteAccountView(generics.DestroyAPIView):
    """DELETE /api/auth/delete/ — Delete the authenticated user's account."""
    permission_classes = [permissions.IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        user = request.user
        username = user.username
        user.delete()
        return Response(
            {'message': f'Account "{username}" has been permanently deleted.'},
            status=status.HTTP_204_NO_CONTENT,
        )


@api_view(['GET', 'PUT'])
def today_prayer_log(request):
    """
    GET  /api/prayers/today/ — Get today's prayer log.
    PUT  /api/prayers/today/ — Update today's prayer log.
    """
    today = get_effective_today()
    log, created = DailyPrayerLog.objects.get_or_create(
        user=request.user,
        date=today,
    )

    if request.method == 'GET':
        serializer = DailyPrayerLogSerializer(log)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = DailyPrayerLogSerializer(log, data=request.data, partial=True)
        if serializer.is_valid():
            updated_log = serializer.save()

            # Recalculate streak from full history (force since prayer log changed)
            streak, _ = Streak.objects.get_or_create(user=request.user)
            streak.recalculate(force=True)

            return Response(DailyPrayerLogSerializer(updated_log).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def prayer_history(request):
    """
    GET /api/prayers/history/?days=7&page=1 — Get prayer logs for the last N days.
    Defaults to 7 days. Maximum 365 days. Paginated with 30 days per page.
    """
    try:
        days = int(request.query_params.get('days', 7))
    except (ValueError, TypeError):
        return Response(
            {'error': 'days parameter must be a valid integer'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Prevent abuse: cap at 365 days
    if days < 1 or days > 365:
        return Response(
            {'error': 'days parameter must be between 1 and 365'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        page = int(request.query_params.get('page', 1))
    except (ValueError, TypeError):
        page = 1

    page_size = 30
    page = max(1, page)

    today = get_effective_today()
    start_date = today - timezone.timedelta(days=days - 1)

    logs = DailyPrayerLog.objects.filter(
        user=request.user,
        date__gte=start_date,
        date__lte=today,
    ).order_by('date')

    # Paginate
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
def streak_view(request):
    """
    GET /api/streak/ — Get the user's current streak info.
    Also checks for streak reset if the user missed a day.
    """
    streak, created = Streak.objects.get_or_create(user=request.user)

    # Full recalculation handles gap-to-today check automatically
    streak.recalculate()

    serializer = StreakSerializer(streak)
    return Response(serializer.data)


@api_view(['POST'])
def log_single_prayer(request):
    """
    POST /api/prayers/log/ — Log a single prayer.
    Body: { "prayer": "fajr", "completed": true, "in_jamaat": false, "location": "home", "date": "2026-04-10" }
    """
    prayer_name = request.data.get('prayer', '').lower()
    completed = request.data.get('completed', True)
    in_jamaat = request.data.get('in_jamaat', False)
    location = request.data.get('location', 'home')
    prayer_status = request.data.get('status', 'on_time')
    reason = request.data.get('reason', None)
    date_str = request.data.get('date', None)

    valid_prayers = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']
    if prayer_name not in valid_prayers:
        return Response(
            {'error': f'Invalid prayer name. Must be one of: {valid_prayers}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate status field
    # Phase 2: Extended to include qada, excused, pending
    valid_statuses = ['on_time', 'late', 'missed', 'qada', 'excused', 'pending']
    if prayer_status not in valid_statuses:
        return Response(
            {'error': f'Invalid status. Must be one of: {valid_statuses}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Sanitize reason field (max 255 chars, strip whitespace)
    if reason:
        reason = str(reason).strip()[:255]

    today = get_effective_today()

    if date_str:
        import datetime
        try:
            target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Expected YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate edit window: only allow today, yesterday, and 2 days ago
        days_ago = (today - target_date).days
        if days_ago < 0:
            return Response(
                {'error': 'Cannot log prayers for future dates.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if days_ago > 2:
            return Response(
                {'error': 'Cannot edit prayers more than 2 days in the past.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        target_date = today

    log, created = DailyPrayerLog.objects.get_or_create(
        user=request.user,
        date=target_date,
    )

    # Update the specific prayer field using explicit field mapping
    # This is safer than setattr and follows Django best practices
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

    # Run Django model validation before saving
    try:
        log.full_clean()
    except DjangoValidationError as e:
        return Response(
            {'error': f'Validation error: {e.message_dict}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    log.save()

    # Recalculate streak from full history (force since prayer log changed)
    streak, _ = Streak.objects.get_or_create(user=request.user)
    streak.recalculate(force=True)

    serializer = DailyPrayerLogSerializer(log)
    return Response(serializer.data)


@api_view(['GET'])
def detailed_prayer_history(request):
    """
    GET /api/prayers/history/detailed/?year=2026&month=4&page=1
    Returns full DailyPrayerLog data for every day in the requested month.
    Used by the calendar heatmap to restore per-prayer colors after reinstall.
    Paginated with 15 days per page.
    """
    today = get_effective_today()

    try:
        year = int(request.query_params.get('year', today.year))
    except (ValueError, TypeError):
        return Response(
            {'error': 'year parameter must be a valid integer'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        month = int(request.query_params.get('month', today.month))
    except (ValueError, TypeError):
        return Response(
            {'error': 'month parameter must be a valid integer'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Clamp to valid ranges
    if month < 1 or month > 12:
        return Response(
            {'error': 'month must be between 1 and 12'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        page = int(request.query_params.get('page', 1))
    except (ValueError, TypeError):
        page = 1

    page_size = 15
    page = max(1, page)

    logs = DailyPrayerLog.objects.filter(
        user=request.user,
        date__year=year,
        date__month=month,
    ).order_by('date')

    # Paginate
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
    """
    GET /api/prayers/reasons/
    Returns aggregated reason counts across all time for the authenticated user.
    Response: { "reasons": { "Work": 5, "Traffic": 3, ... } }
    Optimized: Uses database aggregation instead of loading all logs into memory.
    """
    from django.db.models import Count, Q

    prayer_names = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']
    reason_counts = {}

    for prayer in prayer_names:
        # Use database aggregation for each prayer's reason field
        status_field = f'{prayer}_status'
        reason_field = f'{prayer}_reason'

        # Aggregate reasons where status is 'late' or 'missed' and reason exists
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
def consume_protector_token(request):
    """
    POST /api/streak/consume-token/ — Consume a protector token to save streak.
    Used when a user prays Qada for a missed prayer within 24 hours.

    Sprint 1 (Phase 3 PRD):
    - Weekly limit: 3 token recoveries per week (Sunday 3 AM reset)
    - Anti-gaming: Cannot recover more than 1 day per 24h

    Body: { "date": "2026-04-15" }  (optional, defaults to yesterday)

    Returns the updated streak info.
    """
    from datetime import datetime, timedelta

    streak, _ = Streak.objects.get_or_create(user=request.user)

    # Sprint 1: Check weekly limit + anti-gaming cooldown
    can_use = streak.can_use_token()
    if not can_use['allowed']:
        return Response(
            {'error': can_use['reason'],
             'streak': StreakSerializer(streak).data},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check if tokens available
    if streak.protector_tokens <= 0:
        return Response(
            {'error': 'No protector tokens available. Tokens reset every Sunday.',
             'streak': StreakSerializer(streak).data},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Get the date for which to consume token (defaults to yesterday)
    today = get_effective_today()
    date_str = request.data.get('date')

    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Expected YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        target_date = today - timedelta(days=1)

    # Validate: only yesterday or today allowed
    days_ago = (today - target_date).days
    if days_ago < 0:
        return Response(
            {'error': 'Cannot consume token for future dates.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if days_ago > 1:
        return Response(
            {'error': 'Can only consume token for today or yesterday (Qada must be within 24 hours).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check if the day was actually incomplete
    try:
        log = DailyPrayerLog.objects.get(user=request.user, date=target_date)
        if log.is_valid_for_streak:
            return Response(
                {'error': f'Date {target_date} is already valid for streak. No token needed.',
                 'streak': StreakSerializer(streak).data},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except DailyPrayerLog.DoesNotExist:
        # No log for that date - user needs to create one with Qada prayers
        return Response(
            {'error': f'No prayer log found for {target_date}. Log Qada prayers first.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Consume the token (anti-gaming + weekly limit checks already passed)
    streak.consume_protector_token()

    # Force recalculate streak (the Qada prayers should now count)
    streak.recalculate(force=True)

    return Response({
        'message': f'Protector token consumed for {target_date}.',
        'tokens_remaining': streak.protector_tokens,
        'weekly_tokens_remaining': streak.WEEKLY_TOKEN_LIMIT - streak.weekly_tokens_used,
        'streak': StreakSerializer(streak).data,
    })


@api_view(['POST'])
def set_excused_day(request):
    """
    POST /api/prayers/excused/ — Mark a day as excused (travel, sickness, women's period).
    Sets all prayers on that day to 'excused' status.

    Phase 2: Excused mode feature.
    Body: { "date": "2026-04-15", "reason": "travel" } (optional reason)

    Returns the updated prayer log.
    """
    from datetime import datetime

    date_str = request.data.get('date')
    reason = request.data.get('reason', 'excused')

    if not date_str:
        return Response(
            {'error': 'date is required. Format: YYYY-MM-DD'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response(
            {'error': 'Invalid date format. Expected YYYY-MM-DD.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    today = get_effective_today()
    days_ago = (today - target_date).days

    # Allow setting excused for past days (up to 30 days) and future days (up to 7 days)
    if days_ago < -7:
        return Response(
            {'error': 'Cannot set excused more than 7 days in the future.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if days_ago > 30:
        return Response(
            {'error': 'Cannot set excused more than 30 days in the past.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Get or create the log
    log, created = DailyPrayerLog.objects.get_or_create(
        user=request.user,
        date=target_date,
    )

    # Set all prayers to excused
    excused_reason = reason[:255] if reason else 'excused'
    log.fajr_status = 'excused'
    log.dhuhr_status = 'excused'
    log.asr_status = 'excused'
    log.maghrib_status = 'excused'
    log.isha_status = 'excused'
    log.fajr_reason = excused_reason
    log.dhuhr_reason = excused_reason
    log.asr_reason = excused_reason
    log.maghrib_reason = excused_reason
    log.isha_reason = excused_reason
    # Mark all as completed for streak purposes (excused = valid)
    log.fajr = True
    log.dhuhr = True
    log.asr = True
    log.maghrib = True
    log.isha = True

    log.save()

    # Recalculate streak
    streak, _ = Streak.objects.get_or_create(user=request.user)
    streak.recalculate(force=True)

    return Response(DailyPrayerLogSerializer(log).data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def analytics_view(request):
    """
    GET /api/analytics/weekly/
    Returns per-prayer-type counts for the last 7 days, excluding excused days.
    Response: {
        "fajr": 6, "dhuhr": 5, "asr": 7, "maghrib": 4, "isha": 3,
        "on_time": 10, "late": 5, "missed": 2, "qada": 3,
        "total_valid": 18, "excused_count": 5
    }
    """
    from django.db.models import Count, Q

    today = get_effective_today()
    start_date = today - timezone.timedelta(days=6)

    logs = DailyPrayerLog.objects.filter(
        user=request.user,
        date__gte=start_date,
        date__lte=today,
    )

    counts = {
        'fajr': 0, 'dhuhr': 0, 'asr': 0, 'maghrib': 0, 'isha': 0,
        'on_time': 0, 'late': 0, 'missed': 0, 'qada': 0,
    }
    total_valid = 0
    excused_count = 0

    for log in logs:
        for prayer in ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']:
            status = getattr(log, f'{prayer}_status')
            completed = getattr(log, prayer)

            if status == 'excused':
                counts[prayer] += 1
                excused_count += 1
                total_valid += 1
            elif completed:
                counts[prayer] += 1
                total_valid += 1
                if status in counts:
                    counts[status] += 1

    return Response({**counts, 'total_valid': total_valid, 'excused_count': excused_count})
