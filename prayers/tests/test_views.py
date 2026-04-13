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
        from prayers.views import get_effective_today
        from django.utils import timezone

        effective_today = get_effective_today()
        actual_today = timezone.localtime().date()

        assert effective_today == actual_today