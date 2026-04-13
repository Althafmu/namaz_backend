from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import DailyPrayerLog, Streak
from .serializers import RegisterSerializer, DailyPrayerLogSerializer, StreakSerializer, UserProfileSerializer

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

            # Recalculate streak from full history
            streak, _ = Streak.objects.get_or_create(user=request.user)
            streak.recalculate()

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
    valid_statuses = ['on_time', 'late', 'missed']
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

    # Recalculate streak from full history (handles both completions and un-completions)
    streak, _ = Streak.objects.get_or_create(user=request.user)
    streak.recalculate()

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
