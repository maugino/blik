"""An imported admin must be the same admin as one created any other way.

The import used to grant can_manage_organization alone, straight to the
user: no group, none of the other admin permissions, and nothing added to
the Organization Admin group later.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from accounts.import_service import import_users
from accounts.models import UserProfile
from accounts.permissions import ORG_ADMIN_GROUP, ensure_permission_groups
from core.models import Organization


class ImportedAdminTests(TestCase):
    def setUp(self):
        ensure_permission_groups()
        self.org = Organization.objects.create(name='Acme', email='org@acme.example')

    def _import(self, **user_data):
        return import_users(self.org, [{
            'username': 'imported',
            'email': 'imported@acme.example',
            **user_data,
        }])

    def test_imported_admin_lands_in_the_admin_group(self):
        result = self._import(is_org_admin=True)

        self.assertEqual(result['errors'], [])
        user = User.objects.get(username='imported')
        self.assertTrue(user.groups.filter(name=ORG_ADMIN_GROUP).exists())
        self.assertFalse(user.user_permissions.exists())
        self.assertTrue(user.has_perm('accounts.can_invite_members'))
        self.assertTrue(user.has_perm('accounts.can_delete_organization'))

    def test_imported_member_gets_no_admin_rights(self):
        self._import(is_org_admin=False)

        user = User.objects.get(username='imported')
        self.assertFalse(user.groups.filter(name=ORG_ADMIN_GROUP).exists())
        self.assertFalse(user.has_perm('accounts.can_manage_organization'))


class CrossOrganizationUserTests(TestCase):
    """Usernames are global: an import must never touch a user of another org."""

    def setUp(self):
        ensure_permission_groups()
        self.org = Organization.objects.create(name='Acme', email='org@acme.example')
        other_org = Organization.objects.create(name='Other', email='org@other.example')
        self.victim = User.objects.create_user(username='victim', email='victim@other.example')
        UserProfile.objects.create(user=self.victim, organization=other_org)

    def _import(self, conflict_resolution, **user_data):
        return import_users(self.org, [{
            'username': 'victim',
            'email': 'attacker@acme.example',
            'can_create_cycles_for_others': True,
            **user_data,
        }], conflict_resolution)

    def test_overwrite_leaves_user_of_other_org_unchanged(self):
        result = self._import('overwrite')

        self.victim.refresh_from_db()
        self.assertEqual(self.victim.email, 'victim@other.example')
        self.assertFalse(self.victim.profile.can_create_cycles_for_others)
        self.assertEqual(result['updated'], 0)
        self.assertEqual(result['skipped'], 1)

    def test_duplicate_picks_a_free_username(self):
        User.objects.create_user(username='victim_imported', email='taken@other.example')

        result = self._import('duplicate')

        self.assertEqual(result['errors'], [])
        user = User.objects.get(username='victim_imported2')
        self.assertEqual(user.profile.organization, self.org)

    def test_email_of_another_user_is_not_reused(self):
        result = self._import('skip', username='newcomer', email='Victim@other.example')

        self.assertFalse(User.objects.filter(username='newcomer').exists())
        self.assertEqual(result['skipped'], 1)

    def test_overwrite_cannot_take_the_email_of_another_user(self):
        member = User.objects.create_user(username='member', email='member@acme.example')
        UserProfile.objects.create(user=member, organization=self.org)

        self._import('overwrite', username='member', email='victim@other.example')

        member.refresh_from_db()
        self.assertEqual(member.email, 'member@acme.example')
