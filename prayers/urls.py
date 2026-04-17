from django.urls import path
from . import views

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/offsets/', views.profile_offsets_view, name='profile-offsets'),
    path('user/intent/', views.update_intent_view, name='update-intent'),
    path('user/config/', views.user_behavior_config_view, name='user-config'),
    path('prayers/today/', views.today_prayer_log, name='today-prayer-log'),
    path('prayers/history/', views.prayer_history, name='prayer-history'),
    path('prayers/history/detailed/', views.detailed_prayer_history, name='detailed-prayer-history'),
    path('prayers/reasons/', views.reason_summary, name='reason-summary'),
    path('prayers/log/', views.log_single_prayer, name='log-single-prayer'),
    path('prayers/excused/', views.set_excused_day, name='set-excused-day'),
    path('analytics/weekly/', views.analytics_view, name='analytics-weekly'),
    path('streak/', views.streak_view, name='streak'),
    path('streak/consume-token/', views.consume_protector_token, name='consume-protector-token'),
]
