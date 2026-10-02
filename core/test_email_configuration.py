import os
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import UserProfile
from accounts.permissions import assign_organization_admin
from core.admin import OrganizationAdminForm
from core.models import Organization


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    EMAIL_DELIVERY_METHOD='',
    EMAIL_WEBHOOK_URL='',
    POWER_AUTOMATE_WEBHOOK_URL='',
)
class OrganizationEmailConfigurationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='Test organization',
            email='organization@example.test',
        )
        self.admin_user = User.objects.create_user(
            username='org-admin',
            email='admin@example.test',
            password='test-password',
        )
        UserProfile.objects.create(user=self.admin_user, organization=self.organization)
        assign_organization_admin(self.admin_user)
        self.client.force_login(self.admin_user)

    def isolated_webhook_environment(self, **overrides):
        variables = {
            'EMAIL_DELIVERY_METHOD': '',
            'EMAIL_WEBHOOK_URL': '',
            'POWER_AUTOMATE_WEBHOOK_URL': '',
        }
        variables.update(overrides)
        return patch.dict(os.environ, variables, clear=False)

    def test_webhook_url_is_encrypted_and_decrypts_for_delivery(self):
        webhook_url = 'https://organization.invalid/private-path'

        self.organization.set_email_webhook_url(webhook_url)
        self.organization.save()
        self.organization.refresh_from_db()

        self.assertNotEqual(self.organization.email_webhook_url_encrypted, webhook_url.encode())
        self.assertEqual(self.organization.get_email_webhook_url(), webhook_url)

    def test_webhook_url_is_not_exposed_by_organization_admin_form(self):
        self.organization.set_email_webhook_url('https://organization.invalid/private-path')
        self.organization.save()

        form = OrganizationAdminForm(instance=self.organization)

        self.assertNotIn('email_webhook_url_encrypted', form.fields)
        self.assertEqual(form.fields['email_webhook_url'].initial, None)

    def test_settings_replaces_url_but_never_renders_saved_value(self):
        first_url = 'https://organization.invalid/first'
        replacement_url = 'https://organization.invalid/replacement'

        with self.isolated_webhook_environment():
            response = self.client.post(
                reverse('settings'),
                {
                    'section': 'email',
                    'email_delivery_method': 'http_webhook',
                    'email_webhook_url': first_url,
                },
            )
            self.organization.refresh_from_db()
            self.assertEqual(self.organization.get_email_webhook_url(), first_url)

            response = self.client.get(reverse('settings'))
            self.assertTrue(response.context['webhook_url_configured'])
            self.assertNotContains(response, first_url)

            self.client.post(
                reverse('settings'),
                {
                    'section': 'email',
                    'email_delivery_method': 'http_webhook',
                    'email_webhook_url': replacement_url,
                },
            )

        self.organization.refresh_from_db()
        self.assertEqual(
            self.organization.get_email_webhook_url(),
            replacement_url,
        )

    def test_blank_webhook_replacement_keeps_saved_value(self):
        webhook_url = 'https://organization.invalid/keep'
        self.organization.email_delivery_method = 'http_webhook'
        self.organization.set_email_webhook_url(webhook_url)
        self.organization.save()

        with self.isolated_webhook_environment():
            self.client.post(
                reverse('settings'),
                {
                    'section': 'email',
                    'email_delivery_method': 'http_webhook',
                    'email_webhook_url': '',
                },
            )

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.get_email_webhook_url(), webhook_url)

    @patch('core.email_backends.requests.post')
    def test_test_email_uses_saved_webhook_and_sends_to_admin(self, mock_post):
        webhook_url = 'https://organization.invalid/test'
        self.organization.email_delivery_method = 'http_webhook'
        self.organization.set_email_webhook_url(webhook_url)
        self.organization.save()

        with self.isolated_webhook_environment():
            response = self.client.post(
                reverse('settings'),
                {'section': 'email_test'},
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test email sent to your account email address.')
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args.args[0], webhook_url)
        self.assertEqual(
            mock_post.call_args.kwargs['json']['to'],
            [self.admin_user.email],
        )

    def test_test_email_uses_saved_smtp_configuration(self):
        self.organization.smtp_host = ''
        self.organization.email_delivery_method = 'smtp'
        self.organization.save()

        with self.isolated_webhook_environment():
            response = self.client.post(
                reverse('settings'),
                {'section': 'email_test'},
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test email sent to your account email address.')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.admin_user.email])

    @patch('core.email_backends.requests.post')
    def test_test_email_failure_message_does_not_disclose_webhook_url(self, mock_post):
        webhook_url = 'https://organization.invalid/private-path'
        self.organization.email_delivery_method = 'http_webhook'
        self.organization.set_email_webhook_url(webhook_url)
        self.organization.save()
        mock_post.side_effect = requests.RequestException(f'failed: {webhook_url}')

        with self.isolated_webhook_environment():
            with self.assertLogs('core.email_backends', level='ERROR') as logs:
                response = self.client.post(
                    reverse('settings'),
                    {'section': 'email_test'},
                    follow=True,
                )

        self.assertContains(response, 'Test email could not be sent.')
        self.assertNotContains(response, webhook_url)
        self.assertNotIn(webhook_url, ' '.join(logs.output))

    def test_non_admin_cannot_send_test_email(self):
        user = User.objects.create_user(
            username='member',
            email='member@example.test',
            password='test-password',
        )
        UserProfile.objects.create(user=user, organization=self.organization)
        self.client.force_login(user)

        with patch('core.email.send_email') as mock_send_email:
            response = self.client.post(
                reverse('settings'),
                {'section': 'email_test'},
            )

        self.assertRedirects(response, reverse('settings'))
        mock_send_email.assert_not_called()
