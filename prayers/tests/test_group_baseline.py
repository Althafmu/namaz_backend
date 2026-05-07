"""
Query baseline tests for G1 Group models.
Enforces strict query count assertions.
"""
from django.test import TestCase
from django.test.utils import override_settings
from django.contrib.auth import get_user_model
from prayers.models import Group, GroupMembership, GroupInviteToken
from prayers.domain.constants import GroupRole, GroupPrivacy, GROUP_MAX_MEMBERS

User = get_user_model()


class GroupQueryBaselineTests(TestCase):
    """Query baseline tests for G1 Group models."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )
        self.group = Group.objects.create(
            name='Test Group',
            description='A test group',
            privacy_level=GroupPrivacy.PRIVATE,
            created_by=self.user,
        )
        GroupMembership.objects.create(
            user=self.user,
            group=self.group,
            role=GroupRole.ADMIN,
        )

    @override_settings(DEBUG=True)
    def test_group_list_query_count(self):
        """Baseline: group list with annotations. Must be 1 query."""
        from prayers.selectors import get_group_queryset
        # Pass user so user_is_member gets annotated
        with self.assertNumQueries(1):
            qs = get_group_queryset(user=self.user)
            groups = list(qs)

        self.assertEqual(len(groups), 1)

        # Check annotations exist
        group = groups[0]
        self.assertTrue(hasattr(group, 'member_count'))
        self.assertTrue(hasattr(group, 'user_is_member'))

    @override_settings(DEBUG=True)
    def test_group_detail_query_count(self):
        """Baseline: group detail with annotations. Must be 1 query."""
        from prayers.selectors import get_group_queryset
        with self.assertNumQueries(1):
            qs = get_group_queryset(user=self.user).filter(id=self.group.id)
            group = qs.first()

        self.assertIsNotNone(group)
        self.assertTrue(hasattr(group, 'member_count'))
        self.assertTrue(hasattr(group, 'user_is_member'))

    def test_group_max_members_enforcement(self):
        """Test GROUP_MAX_MEMBERS is enforced."""
        from prayers.services.group_service import user_can_join_group
        from prayers.domain.constants import GROUP_MAX_MEMBERS

        # Fill group to max
        for i in range(GROUP_MAX_MEMBERS):
            u = User.objects.create_user(
                username=f'user{i}@test.com',
                email=f'user{i}@test.com',
                password='pass'
            )
            GroupMembership.objects.create(user=u, group=self.group)

        # Try to add one more
        u_extra = User.objects.create_user(
            username='extra@test.com',
            email='extra@test.com',
            password='pass'
        )
        allowed, reason = user_can_join_group(u_extra, self.group)
        self.assertFalse(allowed)
        self.assertIn('maximum membership limit', reason)
