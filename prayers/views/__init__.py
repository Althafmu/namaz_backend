from prayers.views.auth_views import RegisterView, ProfileView, DeleteAccountView, LogoutView
from prayers.views.prayer_views import (
    today_prayer_log,
    prayer_history,
    detailed_prayer_history,
    reason_summary,
    log_single_prayer,
    set_excused_day,
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

__all__ = [
    "RegisterView",
    "ProfileView",
    "DeleteAccountView",
    "LogoutView",
    "today_prayer_log",
    "prayer_history",
    "detailed_prayer_history",
    "reason_summary",
    "log_single_prayer",
    "set_excused_day",
    "analytics_view",
    "undo_last_prayer_action",
    "sync_status_view",
    "profile_offsets_view",
    "update_intent_view",
    "user_behavior_config_view",
    "pause_notifications_today_view",
    "streak_view",
    "consume_protector_token",
]
