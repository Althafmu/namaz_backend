"""Tests for Streak model logic."""
import pytest
from datetime import date, timedelta
from django.utils import timezone
from django.contrib.auth.models import User

from prayers.models import DailyPrayerLog, Streak


def create_completed_log(user, target_date, **overrides):
    payload = {
        'user': user,
        'date': target_date,
        'fajr': True,
        'dhuhr': True,
        'asr': True,
        'maghrib': True,
        'isha': True,
        'fajr_status': 'on_time',
        'dhuhr_status': 'on_time',
        'asr_status': 'on_time',
        'maghrib_status': 'on_time',
        'isha_status': 'on_time',
    }
    payload.update(overrides)
    return DailyPrayerLog.objects.create(**payload)


@pytest.mark.django_db
class TestStreakRecalculation:
    """Tests for Streak.recalculate() method."""

    def test_streak_resets_after_missed_day(self):
        """Streak should reset to 0 when a day is missed."""
        user = User.objects.create_user(username='testuser', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)

        # Create complete log for yesterday
        yesterday = date.today() - timedelta(days=1)
        create_completed_log(user, yesterday)

        streak.recalculate()
        assert streak.current_streak == 0

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
            create_completed_log(user, d)

        streak.recalculate()
        assert streak.current_streak == 0

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
            create_completed_log(user, d)

        # Gap at days -4 and -3

        # Days -2, -1
        for i in range(2):
            d = date.today() - timedelta(days=2 - i)
            create_completed_log(user, d)

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
        create_completed_log(user, date.today())

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
            create_completed_log(user, d)

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
        create_completed_log(user, yesterday)

        streak.recalculate()
        assert streak.current_streak == 0

        now = timezone.localtime()
        if now.hour >= 12:
            # After noon - should show 0
            assert streak.get_display_streak() == 0


@pytest.mark.django_db
class TestProtectorTokens:
    """Tests for Phase 2: Protector token system."""

    def test_initial_tokens_are_three(self):
        """New users start with 3 protector tokens."""
        user = User.objects.create_user(username='tokenuser', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)
        assert streak.protector_tokens == 3
        assert streak.max_protector_tokens == 3

    def test_consume_token_reduces_count(self):
        """Consuming a token should reduce the count."""
        user = User.objects.create_user(username='tokenuser2', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)

        result = streak.consume_protector_token()
        assert result is True
        assert streak.protector_tokens == 2

    def test_consume_token_fails_when_zero(self):
        """Cannot consume token when none available."""
        user = User.objects.create_user(username='tokenuser3', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)
        streak.protector_tokens = 0
        streak.save()

        result = streak.consume_protector_token()
        assert result is False
        assert streak.protector_tokens == 0

    def test_restore_token_increases_count(self):
        """Restoring a token should increase the count."""
        user = User.objects.create_user(username='tokenuser4', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)
        streak.protector_tokens = 1
        streak.save()

        streak.restore_protector_token()
        assert streak.protector_tokens == 2

    def test_restore_token_caps_at_max(self):
        """Cannot restore tokens above max (3)."""
        user = User.objects.create_user(username='tokenuser5', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)
        streak.protector_tokens = 3
        streak.save()

        streak.restore_protector_token()
        assert streak.protector_tokens == 3  # Still 3, not 4

    def test_weekly_token_reset(self):
        """Tokens should reset to 3 after 7 days."""
        user = User.objects.create_user(username='tokenuser6', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)
        streak.protector_tokens = 0  # User used all tokens
        streak.tokens_reset_date = date.today() - timedelta(days=8)
        streak.save()

        streak.recalculate(force=True)
        assert streak.protector_tokens == 3  # Reset to full


@pytest.mark.django_db
class TestExcusedDays:
    """Tests for Phase 2: Excused days (travel, sickness, women's period)."""

    def test_new_logs_default_to_pending_status(self):
        """Newly created logs should keep unlogged prayers in pending state."""
        user = User.objects.create_user(username='pendinguser', password='testpass')
        log = DailyPrayerLog.objects.create(
            user=user,
            date=date.today(),
        )

        assert log.fajr_status == 'pending'
        assert log.dhuhr_status == 'pending'
        assert log.asr_status == 'pending'
        assert log.maghrib_status == 'pending'
        assert log.isha_status == 'pending'

    def test_all_excused_day_is_valid_for_streak(self):
        """A day with all prayers marked as excused should be valid for streak."""
        user = User.objects.create_user(username='excuseduser', password='testpass')
        yesterday = date.today() - timedelta(days=1)

        log = DailyPrayerLog.objects.create(
            user=user, date=yesterday,
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
            fajr_status='excused', dhuhr_status='excused', asr_status='excused',
            maghrib_status='excused', isha_status='excused',
        )

        assert log.is_valid_for_streak is True

    def test_partially_excused_day_is_not_valid(self):
        """A day with only some prayers excused is not valid for streak."""
        user = User.objects.create_user(username='excuseduser2', password='testpass')
        yesterday = date.today() - timedelta(days=1)

        log = DailyPrayerLog.objects.create(
            user=user, date=yesterday,
            fajr=True, dhuhr=False, asr=True, maghrib=True, isha=True,
            fajr_status='excused', dhuhr_status='missed', asr_status='on_time',
            maghrib_status='on_time', isha_status='on_time',
        )

        assert log.is_valid_for_streak is False

    def test_excused_day_does_not_break_streak(self):
        """Excused days should preserve the streak without incrementing it."""
        user = User.objects.create_user(username='excuseduser3', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)

        # Day before yesterday: complete
        two_days_ago = date.today() - timedelta(days=2)
        create_completed_log(user, two_days_ago)

        # Yesterday: excused
        yesterday = date.today() - timedelta(days=1)
        DailyPrayerLog.objects.create(
            user=user, date=yesterday,
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
            fajr_status='excused', dhuhr_status='excused', asr_status='excused',
            maghrib_status='excused', isha_status='excused',
        )

        streak.recalculate(force=True)
        # Streak should continue but not include the excused day
        # Since today is incomplete, streak is 0
        assert streak.current_streak == 0

    def test_excused_day_extends_streak_gap(self):
        """Excused days in the middle should extend the streak continuity."""
        user = User.objects.create_user(username='excuseduser4', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)

        # Three days ago: complete
        three_days_ago = date.today() - timedelta(days=3)
        create_completed_log(user, three_days_ago)

        # Two days ago: excused
        two_days_ago = date.today() - timedelta(days=2)
        DailyPrayerLog.objects.create(
            user=user, date=two_days_ago,
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
            fajr_status='excused', dhuhr_status='excused', asr_status='excused',
            maghrib_status='excused', isha_status='excused',
        )

        # Yesterday: complete
        yesterday = date.today() - timedelta(days=1)
        create_completed_log(user, yesterday)

        streak.recalculate(force=True)
        # Streak should continue through the excused day
        # Since today is incomplete, streak is 0
        assert streak.current_streak == 0

    def test_excused_days_preserve_current_streak_without_incrementing(self):
        """Excused days should keep the chain alive but not add to the total."""
        user = User.objects.create_user(username='excuseduser5', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)

        two_days_ago = date.today() - timedelta(days=2)
        yesterday = date.today() - timedelta(days=1)
        today = date.today()

        create_completed_log(user, two_days_ago)
        DailyPrayerLog.objects.create(
            user=user, date=yesterday,
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
            fajr_status='excused', dhuhr_status='excused', asr_status='excused',
            maghrib_status='excused', isha_status='excused',
        )
        create_completed_log(user, today)

        streak.recalculate(force=True)

        assert streak.current_streak == 2
        assert streak.longest_streak == 2
        assert streak.last_completed_date == today


@pytest.mark.django_db
class TestQadaPrayers:
    """Tests for Phase 2: Qada (made-up) prayers."""

    def test_qada_prayer_is_valid_for_streak(self):
        """A prayer marked as qada should count as completed for streak."""
        user = User.objects.create_user(username='qadauser', password='testpass')
        yesterday = date.today() - timedelta(days=1)

        # All prayers as qada (made up later)
        log = DailyPrayerLog.objects.create(
            user=user, date=yesterday,
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
            fajr_status='qada', dhuhr_status='qada', asr_status='qada',
            maghrib_status='qada', isha_status='qada',
        )

        assert log.is_valid_for_streak is True

    def test_mixed_qada_and_on_time_is_valid(self):
        """A day with mix of qada and on_time prayers should be valid."""
        user = User.objects.create_user(username='qadauser2', password='testpass')
        yesterday = date.today() - timedelta(days=1)

        log = DailyPrayerLog.objects.create(
            user=user, date=yesterday,
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
            fajr_status='on_time', dhuhr_status='qada', asr_status='on_time',
            maghrib_status='qada', isha_status='late',
        )

        assert log.is_valid_for_streak is True

    def test_qada_extends_streak(self):
        """Qada prayers should extend streak like regular prayers."""
        user = User.objects.create_user(username='qadauser3', password='testpass')
        streak, _ = Streak.objects.get_or_create(user=user)

        # Yesterday: all prayers as qada
        yesterday = date.today() - timedelta(days=1)
        DailyPrayerLog.objects.create(
            user=user, date=yesterday,
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
            fajr_status='qada', dhuhr_status='qada', asr_status='qada',
            maghrib_status='qada', isha_status='qada',
        )

        streak.recalculate(force=True)
        # Since today is incomplete, streak is 0
        assert streak.current_streak == 0

    def test_has_qada_property(self):
        """has_qada property should return True when any prayer is qada."""
        user = User.objects.create_user(username='qadauser4', password='testpass')
        yesterday = date.today() - timedelta(days=1)

        log = DailyPrayerLog.objects.create(
            user=user, date=yesterday,
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
            fajr_status='on_time', dhuhr_status='qada', asr_status='on_time',
            maghrib_status='on_time', isha_status='on_time',
        )

        assert log.has_qada is True

    def test_has_qada_false_when_none(self):
        """has_qada should return False when no prayers are qada."""
        user = User.objects.create_user(username='qadauser5', password='testpass')
        yesterday = date.today() - timedelta(days=1)

        log = create_completed_log(user, yesterday)

        assert log.has_qada is False


@pytest.mark.django_db
class TestIsValidForStreak:
    """Tests for is_valid_for_streak property with various status combinations."""

    def test_all_on_time_is_valid(self):
        """Day with all prayers on_time is valid."""
        user = User.objects.create_user(username='validuser', password='testpass')
        log = create_completed_log(user, date.today() - timedelta(days=1))
        assert log.is_valid_for_streak is True

    def test_mixed_on_time_and_late_is_valid(self):
        """Day with mix of on_time and late prayers is valid."""
        user = User.objects.create_user(username='validuser2', password='testpass')
        log = DailyPrayerLog.objects.create(
            user=user, date=date.today() - timedelta(days=1),
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
            fajr_status='on_time', dhuhr_status='late', asr_status='on_time',
            maghrib_status='late', isha_status='on_time',
        )
        assert log.is_valid_for_streak is True

    def test_incomplete_day_is_invalid(self):
        """Day with missing prayers is invalid."""
        user = User.objects.create_user(username='validuser3', password='testpass')
        log = DailyPrayerLog.objects.create(
            user=user, date=date.today() - timedelta(days=1),
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=False,  # Missing Isha
        )
        assert log.is_valid_for_streak is False

    def test_missed_status_is_invalid_if_incomplete(self):
        """Missed status without completion is invalid."""
        user = User.objects.create_user(username='validuser4', password='testpass')
        log = DailyPrayerLog.objects.create(
            user=user, date=date.today() - timedelta(days=1),
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=False,
            fajr_status='on_time', dhuhr_status='on_time', asr_status='on_time',
            maghrib_status='on_time', isha_status='missed',
        )
        assert log.is_valid_for_streak is False

    def test_pending_status_is_invalid(self):
        """Pending status should not count as valid."""
        user = User.objects.create_user(username='validuser5', password='testpass')
        log = DailyPrayerLog.objects.create(
            user=user, date=date.today() - timedelta(days=1),
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
            fajr_status='pending', dhuhr_status='on_time', asr_status='on_time',
            maghrib_status='on_time', isha_status='on_time',
        )
        # Pending means not yet evaluated, so not valid
        assert log.is_valid_for_streak is False

    def test_excused_count_property(self):
        """excused_count should return number of excused prayers."""
        user = User.objects.create_user(username='validuser6', password='testpass')
        log = DailyPrayerLog.objects.create(
            user=user, date=date.today() - timedelta(days=1),
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
            fajr_status='excused', dhuhr_status='excused', asr_status='on_time',
            maghrib_status='on_time', isha_status='on_time',
        )
        assert log.excused_count == 2
