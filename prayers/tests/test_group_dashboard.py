from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from prayers.models import Group, GroupMembership
from prayers.domain.constants import GroupRole, GroupPrivacy, MembershipStatus

User = get_user_model()


class GroupDashboardTests(TestCase):
    """Query governance tests for G2.1 Group Dashboard."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )
        self.group = Group.objects.create(
            name='Test Group',
            description='A test group for dashboard',
            privacy_level=GroupPrivacy.PRIVATE,
            created_by=self.user,
        )
        GroupMembership.objects.create(
            user=self.user,
            group=self.group,
            role=GroupRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
        # Create some other members with streaks
        for i in range(5):
            u = User.objects.create_user(
                username=f'user{i}@test.com',
                email=f'user{i}@test.com',
                password='pass'
            )
            GroupMembership.objects.create(
                user=u,
                group=self.group,
                role=GroupRole.MEMBER,
                status=MembershipStatus.ACTIVE,
            )

    @override_settings(DEBUG=True)
    def test_dashboard_loads(self):
        """Dashboard endpoint returns 200 with correct shape for authenticated member."""
        client = APIClient()
        client.force_authenticate(user=self.user)

        with self.assertNumQueries(6):
            response = client.get(f'/api/v1/groups/{self.group.id}/dashboard/')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check top-level keys
        self.assertIn('group', data)
        self.assertIn('current_user', data)
        self.assertIn('top_streaks', data)
        self.assertIn('today_completion', data)

        # Check group data
        self.assertEqual(data['group']['id'], self.group.id)
        self.assertEqual(data['group']['name'], 'Test Group')
        self.assertIn('member_count', data['group'])

        # Check current user
        self.assertIsNotNone(data['current_user'])
        self.assertEqual(data['current_user']['role'], GroupRole.ADMIN)

        # Check leaderboard
        self.assertLessEqual(len(data['top_streaks']), 5)

    def test_unauthorized_blocked(self):
        """Non-members cannot access private group dashboard - returns 403."""
        # Create another user who is not a member
        non_member = User.objects.create_user(
            username='nonmember@example.com',
            email='nonmember@example.com',
            password='testpass123'
        )
        client = APIClient()
        client.force_authenticate(user=non_member)

        response = client.get(f'/api/v1/groups/{self.group.id}/dashboard/')
        self.assertEqual(response.status_code, 403)

    def test_public_group_access(self):
        """Public groups can be viewed by anyone (even unauthenticated)."""
        public_group = Group.objects.create(
            name='Public Group',
            privacy_level=GroupPrivacy.PUBLIC,
            created_by=self.user,
        )

        client = APIClient()
        # No authentication - should still work for public groups
        response = client.get(f'/api/v1/groups/{public_group.id}/dashboard/')
        self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=True)
    def test_query_budget(self):
        """Dashboard must stay under 6 queries."""
        client = APIClient()
        client.force_authenticate(user=self.user)

        with self.assertNumQueries(6):
            client.get(f'/api/v1/groups/{self.group.id}/dashboard/')
