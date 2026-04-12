from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone

from .models import DailyPrayerLog, Streak
from .serializers import RegisterSerializer, DailyPrayerLogSerializer, StreakSerializer, UserProfileSerializer

def get_effective_today():
    """
    Returns the effective date for prayer logging.
    Times between midnight and 4:00 AM are attributed to the previous calendar day.
    """
    now = timezone.localtime()
    return (now - timezone.timedelta(hours=4)).date()


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
    GET /api/prayers/history/?days=7 — Get prayer logs for the last N days.
    Defaults to 7 days.
    """
    days = int(request.query_params.get('days', 7))
    today = get_effective_today()
    start_date = today - timezone.timedelta(days=days - 1)

    logs = DailyPrayerLog.objects.filter(
        user=request.user,
        date__gte=start_date,
        date__lte=today,
    ).order_by('date')

    serializer = DailyPrayerLogSerializer(logs, many=True)
    return Response(serializer.data)


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

    if date_str:
        import datetime
        try:
            today = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Expected YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        today = get_effective_today()

    log, created = DailyPrayerLog.objects.get_or_create(
        user=request.user,
        date=today,
    )

    # Update the specific prayer field
    setattr(log, prayer_name, completed)
    setattr(log, f'{prayer_name}_in_jamaat', in_jamaat)
    setattr(log, f'{prayer_name}_status', prayer_status)
    setattr(log, f'{prayer_name}_reason', reason)
    log.location = location
    log.save()

    # Recalculate streak from full history (handles both completions and un-completions)
    streak, _ = Streak.objects.get_or_create(user=request.user)
    streak.recalculate()

    serializer = DailyPrayerLogSerializer(log)
    return Response(serializer.data)


@api_view(['GET'])
def detailed_prayer_history(request):
    """
    GET /api/prayers/history/detailed/?year=2026&month=4
    Returns full DailyPrayerLog data for every day in the requested month.
    Used by the calendar heatmap to restore per-prayer colors after reinstall.
    """
    today = get_effective_today()
    year = int(request.query_params.get('year', today.year))
    month = int(request.query_params.get('month', today.month))

    # Clamp to valid ranges
    if month < 1 or month > 12:
        return Response(
            {'error': 'month must be between 1 and 12'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    logs = DailyPrayerLog.objects.filter(
        user=request.user,
        date__year=year,
        date__month=month,
    ).order_by('date')

    serializer = DailyPrayerLogSerializer(logs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def reason_summary(request):
    """
    GET /api/prayers/reasons/
    Returns aggregated reason counts across all time for the authenticated user.
    Response: { "reasons": { "Work": 5, "Traffic": 3, ... } }
    """
    logs = DailyPrayerLog.objects.filter(user=request.user)

    reason_counts = {}
    prayer_names = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']

    for log in logs:
        for prayer in prayer_names:
            status_val = getattr(log, f'{prayer}_status', 'on_time')
            reason_val = getattr(log, f'{prayer}_reason', None)
            if status_val in ('late', 'missed') and reason_val:
                reason_counts[reason_val] = reason_counts.get(reason_val, 0) + 1

    return Response({'reasons': reason_counts})
