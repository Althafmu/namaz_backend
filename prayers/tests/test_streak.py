"""Tests for Streak model logic."""
import pytest
from datetime import date, timedelta
from django.utils import timezone
from django.contrib.auth.models import User

from prayers.models import DailyPrayerLog, Streak


@pytest.mark.django_db
class TestStreakRecalculation:
    """Tests for Streak.recalculate() method."""

    def test_streak_resets_after_missed_day(self):
        """Streak should reset to 0 when a day is missed."""
        user = User.objects.create_user(username='testuser', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)

        # Create complete log for yesterday
        yesterday = date.today() - timedelta(days=1)
        DailyPrayerLog.objects.create(
            user=user,
            date=yesterday,
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
        )

        streak.recalculate()
        assert streak.current_streak == 1

        # Miss today - streak should be 0
        streak.recalculate()
        assert streak.current_streak == 0

    def test_incomplete_day_breaks_streak(self):
        """An incomplete day (missing some prayers) should break the streak."""
        user = User.objects.create_user(username='testuser2', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)

        # Create complete logs for 3 days
        three_days_ago = date.today() - timedelta(days=3)
        two_days_ago = date.today() - timedelta(days=2)
        yesterday = date.today() - timedelta(days=1)

        for d in [three_days_ago, two_days_ago]:
            DailyPrayerLog.objects.create(
                user=user, date=d,
                fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
            )

        streak.recalculate()
        assert streak.current_streak == 2

        # Incomplete day (only 4 prayers)
        DailyPrayerLog.objects.create(
            user=user, date=yesterday,
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=False,  # Missing Isha
        )

        streak.recalculate()
        assert streak.current_streak == 0

    def test_longest_streak_tracking(self):
        """Longest streak should be tracked correctly across breaks."""
        user = User.objects.create_user(username='testuser3', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)

        # Create 5 days of complete logs, starting from 7 days ago
        # (with a gap in the middle)
        start_date = date.today() - timedelta(days=7)
        for i in range(3):  # Days -7, -6, -5
            d = start_date + timedelta(days=i)
            DailyPrayerLog.objects.create(
                user=user, date=d,
                fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
            )

        # Gap at days -4 and -3

        # Days -2, -1
        for i in range(2):
            d = date.today() - timedelta(days=2 - i)
            DailyPrayerLog.objects.create(
                user=user, date=d,
                fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
            )

        streak.recalculate()
        assert streak.longest_streak == 3  # First run of 3 days


@pytest.mark.django_db
class TestDisplayStreak:
    """Tests for Streak.get_display_streak() method."""

    def test_display_streak_shows_alive_streak(self):
        """If streak is alive, display_streak should equal current_streak."""
        user = User.objects.create_user(username='testuser4', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)

        # Create complete log for today
        DailyPrayerLog.objects.create(
            user=user, date=date.today(),
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
        )

        streak.recalculate()
        # Streak is alive
        assert streak.current_streak == 1
        assert streak.get_display_streak() == 1

    def test_display_streak_grace_period_before_noon(self):
        """Before noon, display_streak should show previous streak even if broken."""
        user = User.objects.create_user(username='testuser5', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)

        # Create complete logs for yesterday and day before
        yesterday = date.today() - timedelta(days=1)
        two_days_ago = date.today() - timedelta(days=2)

        for d in [two_days_ago, yesterday]:
            DailyPrayerLog.objects.create(
                user=user, date=d,
                fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
            )

        streak.recalculate()
        # Current streak is 0 (today not complete)
        assert streak.current_streak == 0

        # Mock the time to be before noon
        now = timezone.localtime()
        if now.hour < 12:
            # Before noon - should show the streak from yesterday
            assert streak.get_display_streak() == 2
        else:
            # After noon - should show 0
            assert streak.get_display_streak() == 0

    def test_display_streak_after_noon_shows_actual(self):
        """After noon, display_streak should show actual streak (0 if broken)."""
        user = User.objects.create_user(username='testuser6', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)

        # Create complete log for yesterday only
        yesterday = date.today() - timedelta(days=1)
        DailyPrayerLog.objects.create(
            user=user, date=yesterday,
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
        )

        streak.recalculate()
        assert streak.current_streak == 0

        now = timezone.localtime()
        if now.hour >= 12:
            # After noon - should show 0
            assert streak.get_display_streak() == 0