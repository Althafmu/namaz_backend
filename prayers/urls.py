from django.urls import path
from . import views

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('prayers/today/', views.today_prayer_log, name='today-prayer-log'),
    path('prayers/history/', views.prayer_history, name='prayer-history'),
    path('prayers/log/', views.log_single_prayer, name='log-single-prayer'),
    path('streak/', views.streak_view, name='streak'),
]
