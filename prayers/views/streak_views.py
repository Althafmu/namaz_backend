from datetime import datetime, timedelta

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from prayers.models import DailyPrayerLog, Streak
from prayers.serializers import StreakSerializer
from prayers.utils.api_errors import error_response
from prayers.utils.time_utils import get_effective_today


@api_view(['GET'])
def streak_view(request):
    streak, _ = Streak.objects.get_or_create(user=request.user)
    streak.recalculate()
    serializer = StreakSerializer(streak)
    return Response(serializer.data)


@api_view(['POST'])
def consume_protector_token(request):
    streak, _ = Streak.objects.get_or_create(user=request.user)
    can_use = streak.can_use_token()
    if not can_use['allowed']:
        return error_response(
            "TOKEN_NOT_ALLOWED",
            can_use['reason'],
            status.HTTP_400_BAD_REQUEST,
            extra={'streak': StreakSerializer(streak).data},
        )
    if streak.protector_tokens <= 0:
        return error_response(
            "NO_TOKENS_AVAILABLE",
            'No protector tokens available. Tokens reset every Sunday.',
            status.HTTP_400_BAD_REQUEST,
            extra={'streak': StreakSerializer(streak).data},
        )

    today = get_effective_today()
    date_str = request.data.get('date')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return error_response("INVALID_DATE_FORMAT", "Invalid date format. Expected YYYY-MM-DD.", status.HTTP_400_BAD_REQUEST)
    else:
        target_date = today - timedelta(days=1)

    days_ago = (today - target_date).days
    if days_ago < 0:
        return error_response("FUTURE_DATE_NOT_ALLOWED", "Cannot consume token for future dates.", status.HTTP_400_BAD_REQUEST)
    if days_ago > 1:
        return error_response("TOKEN_WINDOW_EXCEEDED", "Can only consume token for today or yesterday (Qada must be within 24 hours).", status.HTTP_400_BAD_REQUEST)

    try:
        log = DailyPrayerLog.objects.get(user=request.user, date=target_date)
        if log.is_valid_for_streak or log.is_complete:
            return error_response(
                "DATE_ALREADY_VALID",
                f'Date {target_date} is already valid for streak. No token needed.',
                status.HTTP_400_BAD_REQUEST,
                extra={'streak': StreakSerializer(streak).data},
            )
    except DailyPrayerLog.DoesNotExist:
        return error_response(
            "LOG_NOT_FOUND",
            f'No prayer log found for {target_date}. Log Qada prayers first.',
            status.HTTP_400_BAD_REQUEST,
        )

    streak.consume_protector_token()
    streak.recalculate(force=False, changed_date=target_date)
    return Response({
        'message': f'Protector token consumed for {target_date}.',
        'tokens_remaining': streak.protector_tokens,
        'weekly_tokens_remaining': streak.WEEKLY_TOKEN_LIMIT - streak.weekly_tokens_used,
        'streak': StreakSerializer(streak).data,
    })
