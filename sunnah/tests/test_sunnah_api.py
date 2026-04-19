from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from prayers.models import Streak, UserSettings
from sunnah.models import SunnahLog


@pytest.mark.django_db
class TestSunnahApi:
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='growth_user', password='testpass')
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        settings_obj, _ = UserSettings.objects.get_or_create(user=self.user)
        settings_obj.intent_level = 'growth'
        settings_obj.save(update_fields=['intent_level'])

    def test_log_sunnah_upsert(self):
        self.setUp()
        response = self.client.post(
            '/api/v2/sunnah/log/',
            {'prayer_type': 'fajr', 'completed': True},
            format='json',
        )

        assert response.status_code == 200
        assert response.data['success'] is True
        assert SunnahLog.objects.filter(user=self.user, prayer_type='fajr').count() == 1

        response_2 = self.client.post(
            '/api/v2/sunnah/log/',
            {'prayer_type': 'fajr', 'completed': False},
            format='json',
        )

        assert response_2.status_code == 200
        log = SunnahLog.objects.get(user=self.user, prayer_type='fajr')
        assert log.completed is False

    def test_daily_summary(self):
        self.setUp()
        today = timezone.localdate()
        SunnahLog.objects.create(user=self.user, date=today, prayer_type='fajr', completed=True)
        SunnahLog.objects.create(user=self.user, date=today, prayer_type='dhuhr', completed=True)
        SunnahLog.objects.create(user=self.user, date=today, prayer_type='asr', completed=False)

        response = self.client.get(f'/api/v2/sunnah/daily/?date={today.isoformat()}')

        assert response.status_code == 200
        assert response.data['completed_count'] == 2
        assert response.data['total_opportunities'] == 5
        assert response.data['completion_ratio'] == 0.4
        assert set(response.data['prayer_types_completed']) == {'fajr', 'dhuhr'}

    def test_weekly_summary(self):
        self.setUp()
        today = timezone.localdate()
        sunday = today - timedelta(days=(today.weekday() + 1) % 7)
        SunnahLog.objects.create(user=self.user, date=sunday, prayer_type='fajr', completed=True)
        SunnahLog.objects.create(user=self.user, date=sunday + timedelta(days=1), prayer_type='isha', completed=True)

        response = self.client.get(f'/api/v2/sunnah/weekly/?start_date={sunday.isoformat()}')

        assert response.status_code == 200
        assert response.data['week_start'] == sunday.isoformat()
        assert len(response.data['days']) == 7
        assert response.data['total_completed'] == 2
        assert response.data['total_opportunities'] == 35
        assert response.data['completion_ratio'] == pytest.approx(2 / 35)

    def test_growth_required(self):
        self.setUp()
        settings_obj = UserSettings.objects.get(user=self.user)
        settings_obj.intent_level = 'foundation'
        settings_obj.save(update_fields=['intent_level'])

        response = self.client.post('/api/v2/sunnah/log/', {'prayer_type': 'fajr'}, format='json')

        assert response.status_code == 403
        assert response.data['code'] == 'SUNNAH_GROWTH_REQUIRED'

    def test_invalid_date_format(self):
        self.setUp()
        response = self.client.get('/api/v2/sunnah/daily/?date=19-04-2026')

        assert response.status_code == 400
        assert response.data['code'] == 'INVALID_DATE_FORMAT'

    def test_sunnah_does_not_mutate_streak(self):
        self.setUp()
        streak = Streak.objects.get(user=self.user)
        before_streak = streak.current_streak
        before_tokens = streak.protector_tokens

        response = self.client.post(
            '/api/v2/sunnah/log/',
            {'prayer_type': 'maghrib', 'completed': True},
            format='json',
        )

        assert response.status_code == 200

        streak.refresh_from_db()
        assert streak.current_streak == before_streak
        assert streak.protector_tokens == before_tokens
