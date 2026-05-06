from django.urls import path
from prayers.views.auth_views import RegisterView, ProfileView
from prayers.views.prayer_views import (
    today_prayer_log,
    prayer_history,
    detailed_prayer_history,
    reason_summary,
    log_single_prayer,
    set_excused_day,
    clear_excused_day,
    analytics_view,
    undo_last_prayer_action,
    sync_status_view,
)
from prayers.views.settings_views import (
    profile_offsets_view,
    update_intent_view,
    user_behavior_config_view,
    pause_notifications_today_view,
)
from prayers.views.streak_views import streak_view, consume_protector_token

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/profile/', ProfileView.as_view(), name='profile'),
    path('profile/offsets/', profile_offsets_view, name='profile-offsets'),
    path('user/intent/', update_intent_view, name='update-intent'),
    path('user/config/', user_behavior_config_view, name='user-config'),
    path('prayers/today/', today_prayer_log, name='today-prayer-log'),
    path('prayers/history/', prayer_history, name='prayer-history'),
    path('prayers/history/detailed/', detailed_prayer_history, name='detailed-prayer-history'),
    path('prayers/reasons/', reason_summary, name='reason-summary'),
    path('prayers/log/', log_single_prayer, name='log-single-prayer'),
    path('prayers/excused/', set_excused_day, name='set-excused-day'),
    path('prayers/excused/clear/', clear_excused_day, name='clear-excused-day'),
    path('prayers/log/undo/', undo_last_prayer_action, name='undo-last-prayer-action'),
    # Backward-compatible alias used by older mobile clients.
    path('prayers/undo/', undo_last_prayer_action, name='undo-last-prayer-action-legacy'),
    path('sync/status/', sync_status_view, name='sync-status'),
    # Backward-compatible alias used by older mobile clients.
    path('sync/metadata/', sync_status_view, name='sync-metadata-legacy'),
    path('analytics/weekly/', analytics_view, name='analytics-weekly'),
    path('streak/', streak_view, name='streak'),
    path('streak/consume-token/', consume_protector_token, name='consume-protector-token'),
    path('user/pause-notifications-today/', pause_notifications_today_view, name='pause-notifications-today'),
    # Backward-compatible alias used by older mobile clients.
    path('notifications/pause-today/', pause_notifications_today_view, name='pause-notifications-today-legacy'),
]
