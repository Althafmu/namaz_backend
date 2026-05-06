from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from prayers.utils.time_utils import get_effective_today

from prayers.models import UserSettings
from prayers.serializers import UserSettingsSerializer
from prayers.utils.api_errors import error_response


@api_view(['PATCH'])
@permission_classes([permissions.IsAuthenticated])
def profile_offsets_view(request):
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
    manual_offsets = request.data.get('manual_offsets')
    calculation_method = request.data.get('calculation_method')
    use_hanafi = request.data.get('use_hanafi')
    intent_level = request.data.get('intent_level')
    sunnah_enabled = request.data.get('sunnah_enabled')

    if manual_offsets is not None:
        if not isinstance(manual_offsets, dict):
            return error_response("INVALID_MANUAL_OFFSETS", "manual_offsets must be a JSON object", status.HTTP_400_BAD_REQUEST)
        valid_keys = {'Fajr', 'Sunrise', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'}
        for key, value in manual_offsets.items():
            if key not in valid_keys:
                return error_response("INVALID_OFFSET_KEY", f'Invalid offset key: {key}. Must be one of {valid_keys}', status.HTTP_400_BAD_REQUEST)
            if not isinstance(value, int):
                return error_response("INVALID_OFFSET_VALUE", f'Offset value for {key} must be an integer', status.HTTP_400_BAD_REQUEST)
        settings_obj.manual_offsets = manual_offsets

    if calculation_method is not None:
        settings_obj.calculation_method = str(calculation_method)[:20]

    if use_hanafi is not None:
        settings_obj.use_hanafi = bool(use_hanafi)

    if intent_level is not None:
        if isinstance(intent_level, str):
            intent_level = intent_level.strip().lower()
        valid_intents = {'foundation', 'strengthening', 'growth'}
        if intent_level not in valid_intents:
            return error_response(
                "INVALID_INTENT_LEVEL",
                f'Invalid intent_level. Must be one of: {valid_intents}',
                status.HTTP_400_BAD_REQUEST,
            )
        settings_obj.intent_level = intent_level
        settings_obj.intent_explicitly_set = True

    if sunnah_enabled is not None:
        settings_obj.sunnah_enabled = bool(sunnah_enabled)

    settings_obj.save()
    return Response(UserSettingsSerializer(settings_obj).data)


@api_view(['PATCH'])
@permission_classes([permissions.IsAuthenticated])
def update_intent_view(request):
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
    intent_level = request.data.get('intent_level')
    if intent_level is not None:
        if isinstance(intent_level, str):
            intent_level = intent_level.strip().lower()
        valid_intents = {'foundation', 'strengthening', 'growth'}
        if intent_level not in valid_intents:
            return error_response(
                "INVALID_INTENT_LEVEL",
                f'Invalid intent_level. Must be one of: {valid_intents}',
                status.HTTP_400_BAD_REQUEST,
            )
        settings_obj.intent_level = intent_level
        settings_obj.intent_explicitly_set = True
        settings_obj.save()
        return Response({'success': True, 'data': UserSettingsSerializer(settings_obj).data})
    return error_response("MISSING_INTENT_LEVEL", "intent_level is required", status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_behavior_config_view(request):
    from prayers.services.behavior_service import get_user_behavior_config

    config = get_user_behavior_config(request.user)
    return Response(config)


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def pause_notifications_today_view(request):
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
    today = get_effective_today()

    if request.method == 'POST':
        settings_obj.pause_notifications_until = today
        settings_obj.save(update_fields=['pause_notifications_until'])

    if request.method == 'DELETE':
        settings_obj.pause_notifications_until = None
        settings_obj.save(update_fields=['pause_notifications_until'])

    is_paused = settings_obj.pause_notifications_until == today
    payload = {
        "is_paused": is_paused,
        "paused_until": settings_obj.pause_notifications_until.isoformat()
        if settings_obj.pause_notifications_until
        else None,
    }
    if request.method == 'POST':
        payload["message"] = "Notifications paused for today"
    if request.method == 'DELETE':
        payload["message"] = "Notifications resumed"
    return Response(payload)
