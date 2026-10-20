"""The JSON endpoints called from fetch() must not answer with HTML.

Django's login_required sends an expired session to the login page; the
caller follows the redirect and fails parsing the markup. These views use
@login_required(as_json=True) instead.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from core.models import Organization


class AnonymousJsonEndpointTests(TestCase):
    """Called without a session — as an expired one would be."""

    def setUp(self):
        # SetupMiddleware sends every request to /setup/ until an
        # organization and a profile exist.
        org = Organization.objects.create(name='Acme', email='org@acme.example')
        user = User.objects.create_user(
            username='someone', email='someone@acme.example', password='pw')
        UserProfile.objects.create(user=user, organization=org)

    def test_mark_welcome_seen_answers_json(self):
        response = self.client.post(reverse('account:mark_welcome_seen'))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_preview_import_answers_json(self):
        response = self.client.post(reverse('account:preview_import'))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_export_data_still_redirects_to_the_login_page(self):
        """Reached by a plain link, so the browser should go and log in."""
        response = self.client.get(reverse('account:export_data'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
