"""
Query baseline tests for G1 Group models.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from prayers.models import Group, GroupMembership, GroupInviteToken
from prayers.domain.constants import GroupRole, GroupPrivacy

User = get_user_model()


class GroupModelTests(TestCase):
    """Test Group models work correctly."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123',
        )
        self.group = Group.objects.create(
            name='Test Group',
            description='A test group',
            privacy_level=GroupPrivacy.PRIVATE,
            created_by=self.user,
        )

    def test_group_creation(self):
        """Test Group model creation."""
        self.assertEqual(self.group.name, 'Test Group')
        self.assertEqual(self.group.privacy_level, GroupPrivacy.PRIVATE)
        self.assertEqual(self.group.created_by, self.user)

    def test_group_membership_creation(self):
        """Test GroupMembership model creation."""
        membership = GroupMembership.objects.create(
            user=self.user,
            group=self.group,
            role=GroupRole.ADMIN,
        )
        self.assertEqual(membership.role, GroupRole.ADMIN)
        self.assertTrue(membership.is_admin)
        self.assertTrue(membership.is_member)

    def test_group_invite_token_creation(self):
        """Test GroupInviteToken with hashed tokens."""
        token = GroupInviteToken.objects.create(
            group=self.group,
            token_hash='test_hash_123',
            created_by=self.user,
        )
        self.assertEqual(token.token_hash, 'test_hash_123')
        self.assertFalse(token.is_revoked)
        self.assertTrue(token.is_valid())

    def test_unique_constraint(self):
        """Test unique constraint on user+group."""
        GroupMembership.objects.create(
            user=self.user,
            group=self.group,
            role=GroupRole.ADMIN,
        )
        # Try to create duplicate - should fail
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            GroupMembership.objects.create(
                user=self.user,
                group=self.group,
                role=GroupRole.MEMBER,
            )

    def test_selector_annotations(self):
        """Test that selectors properly annotate counts."""
        # Add a member
        GroupMembership.objects.create(
            user=self.user,
            group=self.group,
            role=GroupRole.ADMIN,
        )

        # Test get_group_queryset annotations
        from prayers.selectors import get_group_queryset
        qs = get_group_queryset()
        group = qs.first()
        self.assertIsNotNone(group)
        # member_count should be annotated
        self.assertTrue(hasattr(group, 'member_count'))
        self.assertEqual(group.member_count, 1)
