from datetime import timedelta

from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from prayers.models import UserSettings
from prayers.utils.api_errors import error_response
from prayers.utils.time_utils import get_effective_today
from sunnah.models import SunnahLog
from sunnah.serializers import SunnahLogSerializer, SunnahLogWriteSerializer


def _ensure_growth_intent(user):
    settings_obj, _ = UserSettings.objects.get_or_create(user=user)
    return settings_obj.intent_level == 'growth'


def _parse_date_or_today(raw_date):
    if not raw_date:
        return get_effective_today()
    try:
        return timezone.datetime.strptime(raw_date, '%Y-%m-%d').date()
    except ValueError:
        return None


def _day_summary(user, target_date):
    logs = SunnahLog.objects.filter(user=user, date=target_date, completed=True)
    completed_prayer_types = list(logs.values_list('prayer_type', flat=True))
    total_opportunities = len(SunnahLog.PRAYER_TYPE_CHOICES)
    completed_count = len(completed_prayer_types)
    completion_ratio = completed_count / total_opportunities if total_opportunities else 0.0
    return {
        'date': target_date.isoformat(),
        'completed_count': completed_count,
        'total_opportunities': total_opportunities,
        'completion_ratio': completion_ratio,
        'prayer_types_completed': completed_prayer_types,
    }


def _sunday_week_start(target_date):
    days_since_sunday = (target_date.weekday() + 1) % 7
    return target_date - timedelta(days=days_since_sunday)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def sunnah_log_view(request):
    if not _ensure_growth_intent(request.user):
        return error_response(
            'SUNNAH_GROWTH_REQUIRED',
            'Sunna tracking is only available for Growth intent level.',
            status.HTTP_403_FORBIDDEN,
        )

    serializer = SunnahLogWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    target_date = serializer.validated_data.get('date') or get_effective_today()
    prayer_type = serializer.validated_data['prayer_type']
    completed = serializer.validated_data.get('completed', True)

    log, _ = SunnahLog.objects.update_or_create(
        user=request.user,
        date=target_date,
        prayer_type=prayer_type,
        defaults={'completed': completed},
    )

    return Response({'success': True, 'data': SunnahLogSerializer(log).data})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def sunnah_daily_view(request):
    if not _ensure_growth_intent(request.user):
        return error_response(
            'SUNNAH_GROWTH_REQUIRED',
            'Sunna tracking is only available for Growth intent level.',
            status.HTTP_403_FORBIDDEN,
        )

    target_date = _parse_date_or_today(request.query_params.get('date'))
    if target_date is None:
        return error_response(
            'INVALID_DATE_FORMAT',
            'Invalid date format. Expected YYYY-MM-DD.',
            status.HTTP_400_BAD_REQUEST,
        )

    return Response(_day_summary(request.user, target_date))


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def sunnah_weekly_view(request):
    if not _ensure_growth_intent(request.user):
        return error_response(
            'SUNNAH_GROWTH_REQUIRED',
            'Sunna tracking is only available for Growth intent level.',
            status.HTTP_403_FORBIDDEN,
        )

    raw_start_date = request.query_params.get('start_date')
    if raw_start_date:
        week_start = _parse_date_or_today(raw_start_date)
        if week_start is None:
            return error_response(
                'INVALID_DATE_FORMAT',
                'Invalid date format. Expected YYYY-MM-DD.',
                status.HTTP_400_BAD_REQUEST,
            )
    else:
        week_start = _sunday_week_start(get_effective_today())

    days = []
    total_completed = 0
    total_opportunities = 0
    for day_offset in range(7):
        day = week_start + timedelta(days=day_offset)
        summary = _day_summary(request.user, day)
        days.append(summary)
        total_completed += summary['completed_count']
        total_opportunities += summary['total_opportunities']

    completion_ratio = total_completed / total_opportunities if total_opportunities else 0.0

    return Response(
        {
            'week_start': week_start.isoformat(),
            'week_end': (week_start + timedelta(days=6)).isoformat(),
            'days': days,
            'total_completed': total_completed,
            'total_opportunities': total_opportunities,
            'completion_ratio': completion_ratio,
        }
    )
