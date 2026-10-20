"""The setup page must produce the same admin as every other path.

It used to grant three permissions straight to the user, leaving the
account in no group: later additions to the Organization Admin group then
passed it by, and can_delete_organization never arrived at all.
"""
from io import StringIO

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from accounts.permissions import (
    ORG_ADMIN_GROUP,
    ORG_MEMBER_GROUP,
    assign_organization_member,
    ensure_permission_groups,
)
from core.models import Organization
from core.upgrade_steps import _move_setup_admins_into_the_admin_group

ADMIN_PERMISSIONS = [
    'accounts.can_invite_members',
    'accounts.can_manage_organization',
    'accounts.can_delete_organization',
    'accounts.can_view_all_reports',
]


def grant_directly(user, *codenames):
    """Grant permissions on the user itself, the way setup used to."""
    content_type = ContentType.objects.get_for_model(UserProfile)
    user.user_permissions.add(*Permission.objects.filter(
        content_type=content_type, codename__in=codenames))


class SetupCreatesAGroupedAdminTests(TestCase):
    def setUp(self):
        ensure_permission_groups()
        self.user = User.objects.create_user(
            username='founder', email='founder@acme.example', password='pw')
        self.client.force_login(self.user)

    def _run_setup(self):
        return self.client.post(reverse('setup_organization'), {
            'name': 'Acme',
            'email': 'org@acme.example',
        })

    def test_setup_admin_lands_in_the_admin_group(self):
        self._run_setup()

        self.assertTrue(
            User.objects.get(pk=self.user.pk).groups.filter(
                name=ORG_ADMIN_GROUP).exists())

    def test_setup_admin_holds_every_admin_permission(self):
        """can_delete_organization was missing from the hand-written list."""
        self._run_setup()

        user = User.objects.get(pk=self.user.pk)
        for permission in ADMIN_PERMISSIONS:
            self.assertTrue(user.has_perm(permission), permission)

    def test_setup_admin_carries_no_direct_grants(self):
        self._run_setup()

        self.assertFalse(
            User.objects.get(pk=self.user.pk).user_permissions.exists())


class UpgradeStepTests(TestCase):
    def setUp(self):
        ensure_permission_groups()
        self.org = Organization.objects.create(name='Acme', email='org@acme.example')

    def _make_legacy_admin(self, username='legacy'):
        """An account as the old setup page left it: permissions, no group."""
        user = User.objects.create_user(
            username=username, email=f'{username}@acme.example', password='pw')
        UserProfile.objects.create(user=user, organization=self.org)
        grant_directly(user, 'can_invite_members', 'can_manage_organization',
                       'can_view_all_reports')
        return user

    def _run_step(self):
        _move_setup_admins_into_the_admin_group(StringIO())

    def test_legacy_admin_joins_the_group(self):
        user = self._make_legacy_admin()

        self._run_step()

        self.assertTrue(
            User.objects.get(pk=user.pk).groups.filter(name=ORG_ADMIN_GROUP).exists())

    def test_legacy_admin_gains_the_permissions_it_was_missing(self):
        user = self._make_legacy_admin()
        self.assertFalse(
            User.objects.get(pk=user.pk).has_perm('accounts.can_delete_organization'))

        self._run_step()

        user = User.objects.get(pk=user.pk)
        for permission in ADMIN_PERMISSIONS:
            self.assertTrue(user.has_perm(permission), permission)

    def test_direct_grants_are_cleared_once_the_group_covers_them(self):
        user = self._make_legacy_admin()

        self._run_step()

        self.assertFalse(User.objects.get(pk=user.pk).user_permissions.exists())

    def test_a_members_own_grant_is_left_alone(self):
        """The team UI grants can_view_all_reports per user — do not undo that."""
        member = User.objects.create_user(
            username='member', email='member@acme.example', password='pw')
        UserProfile.objects.create(user=member, organization=self.org)
        assign_organization_member(member)
        grant_directly(member, 'can_view_all_reports')

        self._run_step()

        member = User.objects.get(pk=member.pk)
        self.assertTrue(member.has_perm('accounts.can_view_all_reports'))
        self.assertTrue(member.user_permissions.filter(
            codename='can_view_all_reports').exists())
        self.assertTrue(member.groups.filter(name=ORG_MEMBER_GROUP).exists())
        self.assertFalse(member.groups.filter(name=ORG_ADMIN_GROUP).exists())

    def test_a_demoted_admin_stays_a_member(self):
        """Demotion used to leave the direct grant; the step must not undo it."""
        user = self._make_legacy_admin('demoted')
        assign_organization_member(user)
        grant_directly(user, 'can_manage_organization')  # as the old demotion left it

        self._run_step()

        user = User.objects.get(pk=user.pk)
        self.assertFalse(user.groups.filter(name=ORG_ADMIN_GROUP).exists())
        self.assertTrue(user.groups.filter(name=ORG_MEMBER_GROUP).exists())
        self.assertFalse(user.has_perm('accounts.can_manage_organization'))

    def test_running_it_twice_changes_nothing(self):
        user = self._make_legacy_admin()

        self._run_step()
        self._run_step()

        user = User.objects.get(pk=user.pk)
        self.assertEqual(user.groups.filter(name=ORG_ADMIN_GROUP).count(), 1)
        self.assertTrue(user.has_perm('accounts.can_manage_organization'))

    def test_a_properly_grouped_admin_is_untouched(self):
        user = User.objects.create_user(
            username='grouped', email='grouped@acme.example', password='pw')
        UserProfile.objects.create(user=user, organization=self.org)
        from accounts.permissions import assign_organization_admin
        assign_organization_admin(user)

        self._run_step()

        user = User.objects.get(pk=user.pk)
        self.assertTrue(user.groups.filter(name=ORG_ADMIN_GROUP).exists())
        self.assertFalse(user.user_permissions.exists())
