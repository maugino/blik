"""Permission smoke tests for the reviewee views in blik/admin_views.py.

These three views used to check the permission inline; the checks now sit in
decorators. The tests pin down what the checks do, not how they are written.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Reviewee, UserProfile
from accounts.permissions import (
    assign_organization_admin,
    assign_organization_member,
    ensure_permission_groups,
)
from core.models import Organization
from questionnaires.models import Questionnaire
from reviews.models import ReviewCycle


class RevieweeViewPermissionTestCase(TestCase):
    def setUp(self):
        ensure_permission_groups()
        self.org = Organization.objects.create(name='Acme', email='org@acme.example')

        self.admin = User.objects.create_user(
            username='admin', email='admin@acme.example', password='pw')
        UserProfile.objects.create(user=self.admin, organization=self.org)
        assign_organization_admin(self.admin)

        self.member = User.objects.create_user(
            username='member', email='member@acme.example', password='pw')
        UserProfile.objects.create(user=self.member, organization=self.org)
        assign_organization_member(self.member)

        self.reviewee = Reviewee.objects.create(
            organization=self.org, name='Dana Doe', email='dana@acme.example')


class RevieweeEditAccessTests(RevieweeViewPermissionTestCase):
    def _url(self):
        return reverse('reviewee_edit', args=[self.reviewee.id])

    def test_member_is_redirected_to_the_reviewee_list(self):
        self.client.force_login(self.member)
        response = self.client.get(self._url())
        self.assertRedirects(response, reverse('reviewee_list'))

    def test_member_cannot_rename_a_reviewee(self):
        self.client.force_login(self.member)
        self.client.post(self._url(), {'name': 'Renamed', 'email': 'dana@acme.example'})

        self.reviewee.refresh_from_db()
        self.assertEqual(self.reviewee.name, 'Dana Doe')

    def test_admin_can_rename_a_reviewee(self):
        self.client.force_login(self.admin)
        self.client.post(self._url(), {'name': 'Renamed', 'email': 'dana@acme.example'})

        self.reviewee.refresh_from_db()
        self.assertEqual(self.reviewee.name, 'Renamed')


class RevieweeDeleteAccessTests(RevieweeViewPermissionTestCase):
    def _url(self):
        return reverse('reviewee_delete', args=[self.reviewee.id])

    def test_member_cannot_deactivate_a_reviewee(self):
        self.client.force_login(self.member)
        self.client.post(self._url())

        self.reviewee.refresh_from_db()
        self.assertTrue(self.reviewee.is_active)

    def test_admin_can_deactivate_a_reviewee(self):
        self.client.force_login(self.admin)
        self.client.post(self._url())

        self.reviewee.refresh_from_db()
        self.assertFalse(self.reviewee.is_active)


class QuickCycleCreateAccessTests(RevieweeViewPermissionTestCase):
    def setUp(self):
        super().setUp()
        self.questionnaire = Questionnaire.objects.create(
            name='Professional Skills', organization=self.org)

    def _url(self):
        return reverse('quick_cycle_create', args=[self.reviewee.id])

    def test_member_cannot_start_a_cycle_for_someone_else(self):
        self.client.force_login(self.member)
        self.client.post(self._url(), {'questionnaire_id': self.questionnaire.id})

        self.assertFalse(ReviewCycle.objects.filter(reviewee=self.reviewee).exists())

    def test_admin_can_start_a_cycle(self):
        self.client.force_login(self.admin)
        self.client.post(self._url(), {'questionnaire_id': self.questionnaire.id})

        self.assertTrue(ReviewCycle.objects.filter(reviewee=self.reviewee).exists())

    def test_require_post_runs_before_the_permission_check(self):
        """A member GETting the URL gets 405, not the permission redirect."""
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self._url()).status_code, 405)
