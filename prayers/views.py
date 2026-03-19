from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone

from .models import DailyPrayerLog, Streak
from .serializers import RegisterSerializer, DailyPrayerLogSerializer, StreakSerializer, UserProfileSerializer


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
    today = timezone.now().date()
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

            # Update streak if all prayers are now complete
            if updated_log.is_complete:
                streak, _ = Streak.objects.get_or_create(user=request.user)
                streak.update_streak(today)

            return Response(DailyPrayerLogSerializer(updated_log).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def prayer_history(request):
    """
    GET /api/prayers/history/?days=7 — Get prayer logs for the last N days.
    Defaults to 7 days.
    """
    days = int(request.query_params.get('days', 7))
    today = timezone.now().date()
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

    # Check if streak should be reset (missed yesterday)
    streak.check_and_reset()

    serializer = StreakSerializer(streak)
    return Response(serializer.data)


@api_view(['POST'])
def log_single_prayer(request):
    """
    POST /api/prayers/log/ — Log a single prayer.
    Body: { "prayer": "fajr", "completed": true, "in_jamaat": false, "location": "home" }
    """
    prayer_name = request.data.get('prayer', '').lower()
    completed = request.data.get('completed', True)
    in_jamaat = request.data.get('in_jamaat', False)
    location = request.data.get('location', 'home')

    valid_prayers = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']
    if prayer_name not in valid_prayers:
        return Response(
            {'error': f'Invalid prayer name. Must be one of: {valid_prayers}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    today = timezone.now().date()
    log, created = DailyPrayerLog.objects.get_or_create(
        user=request.user,
        date=today,
    )

    # Update the specific prayer field
    setattr(log, prayer_name, completed)
    setattr(log, f'{prayer_name}_in_jamaat', in_jamaat)
    log.location = location
    log.save()

    # Update streak if all prayers are now complete
    if log.is_complete:
        streak, _ = Streak.objects.get_or_create(user=request.user)
        streak.update_streak(today)

    serializer = DailyPrayerLogSerializer(log)
    return Response(serializer.data)
