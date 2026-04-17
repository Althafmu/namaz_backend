"""Tests for prayer views - edit window validation."""
import pytest
from datetime import date, timedelta
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from prayers.models import DailyPrayerLog, Streak


@pytest.mark.django_db
class TestEditWindowValidation:
    """Tests for the 2-day edit window restriction."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_cannot_log_future_dates(self):
        """Should reject attempts to log prayers for future dates."""
        self.setUp()
        tomorrow = date.today() + timedelta(days=1)

        response = self.client.post('/api/prayers/log/', {
            'prayer': 'fajr',
            'completed': True,
            'date': tomorrow.isoformat(),
        })

        assert response.status_code == 400
        assert 'future' in str(response.data['error']).lower()

    def test_cannot_edit_beyond_2_days(self):
        """Should reject attempts to edit prayers more than 2 days in the past."""
        self.setUp()
        three_days_ago = date.today() - timedelta(days=3)

        response = self.client.post('/api/prayers/log/', {
            'prayer': 'fajr',
            'completed': True,
            'date': three_days_ago.isoformat(),
        })

        assert response.status_code == 400
        assert '2 days' in str(response.data['error'])

    def test_can_edit_yesterday(self):
        """Should allow editing yesterday's prayers."""
        self.setUp()
        yesterday = date.today() - timedelta(days=1)

        response = self.client.post('/api/prayers/log/', {
            'prayer': 'fajr',
            'completed': True,
            'date': yesterday.isoformat(),
        })

        assert response.status_code == 200

    def test_can_edit_two_days_ago(self):
        """Should allow editing prayers from 2 days ago."""
        self.setUp()
        two_days_ago = date.today() - timedelta(days=2)

        response = self.client.post('/api/prayers/log/', {
            'prayer': 'fajr',
            'completed': True,
            'date': two_days_ago.isoformat(),
        })

        assert response.status_code == 200

    def test_can_edit_today(self):
        """Should allow editing today's prayers."""
        self.setUp()

        response = self.client.post('/api/prayers/log/', {
            'prayer': 'fajr',
            'completed': True,
        })

        assert response.status_code == 200

    def test_edit_updates_target_date(self):
        """Editing a past date should update that date's log, not today's."""
        self.setUp()
        yesterday = date.today() - timedelta(days=1)

        # Log for yesterday
        response = self.client.post('/api/prayers/log/', {
            'prayer': 'fajr',
            'completed': True,
            'date': yesterday.isoformat(),
        })

        assert response.status_code == 200
        log = DailyPrayerLog.objects.get(user=self.user, date=yesterday)
        assert log.fajr is True

        # Today's log should not exist
        assert not DailyPrayerLog.objects.filter(user=self.user, date=date.today()).exists()


@pytest.mark.django_db
class TestDayRollover:
    """Tests for midnight day rollover."""

    def test_get_effective_today_returns_current_date(self):
        """get_effective_today should return the current date (midnight rollover)."""
        from prayers.utils.time_utils import get_effective_today
        from django.utils import timezone

        effective_today = get_effective_today()
        actual_today = timezone.localtime().date()

        assert effective_today == actual_today


@pytest.mark.django_db
class TestConsumeProtectorToken:
    """Tests for POST /api/streak/consume-token/ endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='tokenuser', password='testpass')
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_consume_token_success(self):
        """Should successfully consume a token and update streak."""
        self.setUp()
        # Create an incomplete day yesterday
        yesterday = date.today() - timedelta(days=1)
        DailyPrayerLog.objects.create(
            user=self.user, date=yesterday,
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=False,
            fajr_status='on_time', dhuhr_status='on_time', asr_status='on_time',
            maghrib_status='on_time', isha_status='missed',
        )

        response = self.client.post('/api/streak/consume-token/')

        assert response.status_code == 200
        assert 'tokens_remaining' in response.data
        assert response.data['tokens_remaining'] == 2

    def test_consume_token_fails_when_zero(self):
        """Should fail when no tokens available."""
        self.setUp()
        streak, _ = Streak.objects.get_or_create(user=self.user)
        streak.protector_tokens = 0
        streak.save()

        response = self.client.post('/api/streak/consume-token/')

        assert response.status_code == 400
        assert 'No protector tokens available' in response.data['error']

    def test_consume_token_fails_for_future_date(self):
        """Should fail when trying to consume token for future date."""
        self.setUp()
        tomorrow = date.today() + timedelta(days=1)

        response = self.client.post('/api/streak/consume-token/', {
            'date': tomorrow.isoformat(),
        })

        assert response.status_code == 400
        assert 'future' in response.data['error'].lower()

    def test_consume_token_fails_for_old_date(self):
        """Should fail when trying to consume token for date more than 1 day ago."""
        self.setUp()
        two_days_ago = date.today() - timedelta(days=2)

        response = self.client.post('/api/streak/consume-token/', {
            'date': two_days_ago.isoformat(),
        })

        assert response.status_code == 400
        assert '24 hours' in response.data['error']

    def test_consume_token_fails_for_already_valid_day(self):
        """Should fail when day is already valid for streak."""
        self.setUp()
        yesterday = date.today() - timedelta(days=1)
        DailyPrayerLog.objects.create(
            user=self.user, date=yesterday,
            fajr=True, dhuhr=True, asr=True, maghrib=True, isha=True,
        )

        response = self.client.post('/api/streak/consume-token/', {
            'date': yesterday.isoformat(),
        })

        assert response.status_code == 400
        assert 'already valid' in response.data['error'].lower()


@pytest.mark.django_db
class TestSetExcusedDay:
    """Tests for POST /api/prayers/excused/ endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='excuseduser', password='testpass')
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_set_excused_day_success(self):
        """Should mark all prayers as excused for a date."""
        self.setUp()
        yesterday = date.today() - timedelta(days=1)

        response = self.client.post('/api/prayers/excused/', {
            'date': yesterday.isoformat(),
            'reason': 'travel',
        })

        assert response.status_code == 200
        log = DailyPrayerLog.objects.get(user=self.user, date=yesterday)
        assert log.fajr_status == 'excused'
        assert log.dhuhr_status == 'excused'
        assert log.asr_status == 'excused'
        assert log.maghrib_status == 'excused'
        assert log.isha_status == 'excused'
        assert log.fajr_reason == 'travel'

    def test_set_excused_day_future_limit(self):
        """Should fail for dates more than 7 days in future."""
        self.setUp()
        future_date = date.today() + timedelta(days=8)

        response = self.client.post('/api/prayers/excused/', {
            'date': future_date.isoformat(),
        })

        assert response.status_code == 400
        assert '7 days' in response.data['error']

    def test_set_excused_day_past_limit(self):
        """Should fail for dates more than 30 days in past."""
        self.setUp()
        past_date = date.today() - timedelta(days=31)

        response = self.client.post('/api/prayers/excused/', {
            'date': past_date.isoformat(),
        })

        assert response.status_code == 400
        assert '30 days' in response.data['error']

    def test_set_excused_day_requires_date(self):
        """Should fail when date is not provided."""
        self.setUp()

        response = self.client.post('/api/prayers/excused/', {})

        assert response.status_code == 400
        assert 'date is required' in response.data['error']

    def test_set_excused_day_marks_prayers_complete(self):
        """Should mark all prayers as complete (True) for streak purposes."""
        self.setUp()
        yesterday = date.today() - timedelta(days=1)

        response = self.client.post('/api/prayers/excused/', {
            'date': yesterday.isoformat(),
        })

        assert response.status_code == 200
        log = DailyPrayerLog.objects.get(user=self.user, date=yesterday)
        assert log.fajr is True
        assert log.dhuhr is True
        assert log.asr is True
        assert log.maghrib is True
        assert log.isha is True
        assert log.is_valid_for_streak is True


@pytest.mark.django_db
class TestLogPrayerWithStatus:
    """Tests for logging prayers with status (qada, late, etc.)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='statususer', password='testpass')
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_log_prayer_with_qada_status(self):
        """Should allow logging prayer with qada status."""
        self.setUp()

        response = self.client.post('/api/prayers/log/', {
            'prayer': 'fajr',
            'completed': True,
            'status': 'qada',
        })

        assert response.status_code == 200
        log = DailyPrayerLog.objects.get(user=self.user, date=date.today())
        assert log.fajr_status == 'qada'

    def test_log_prayer_with_excused_status(self):
        """Should allow logging prayer with excused status."""
        self.setUp()

        response = self.client.post('/api/prayers/log/', {
            'prayer': 'fajr',
            'completed': True,
            'status': 'excused',
        })

        assert response.status_code == 200
        log = DailyPrayerLog.objects.get(user=self.user, date=date.today())
        assert log.fajr_status == 'excused'

    def test_log_prayer_with_invalid_status(self):
        """Should reject invalid status values."""
        self.setUp()

        response = self.client.post('/api/prayers/log/', {
            'prayer': 'fajr',
            'completed': True,
            'status': 'invalid_status',
        })

        assert response.status_code == 400
        assert 'Invalid status' in response.data['error']

    def test_log_prayer_with_reason(self):
        """Should allow logging prayer with reason."""
        self.setUp()

        response = self.client.post('/api/prayers/log/', {
            'prayer': 'fajr',
            'completed': True,
            'status': 'late',
            'reason': 'Work meeting ran late',
        })

        assert response.status_code == 200
        log = DailyPrayerLog.objects.get(user=self.user, date=date.today())
        assert log.fajr_status == 'late'
        assert log.fajr_reason == 'Work meeting ran late'