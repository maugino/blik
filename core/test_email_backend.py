"""Tests for `core.email`.

The organization's SMTP settings take priority, but when they are absent the
fallback must be the backend from Django settings — not a hardcoded SMTP
connection. Hardcoding SMTP means the console backend never prints and the
locmem backend never fills mail.outbox, so email fails in dev and in tests
regardless of EMAIL_BACKEND.
"""
from unittest.mock import patch

from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.locmem import EmailBackend as LocmemBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend
from django.test import TestCase, override_settings

from core.email import get_email_backend, send_email
from core.email_backends import HTTPWebhookBackend
from core.factories import OrganizationFactory


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    EMAIL_DELIVERY_METHOD='',
    EMAIL_WEBHOOK_URL='',
    POWER_AUTOMATE_WEBHOOK_URL='',
)
class GetEmailBackendTests(TestCase):
    def test_existing_organization_defaults_to_smtp(self):
        organization = OrganizationFactory()

        self.assertEqual(organization.email_delivery_method, 'smtp')

    def test_falls_back_to_configured_backend_when_org_has_no_smtp_host(self):
        OrganizationFactory(smtp_host='')

        # Tests run under the locmem backend; a hardcoded SMTP backend here
        # would try to open a socket to EMAIL_HOST.
        self.assertIsInstance(get_email_backend(), LocmemBackend)

    def test_organization_smtp_settings_take_priority(self):
        OrganizationFactory(smtp_host='smtp.acme.example.com', smtp_port=2525)

        backend = get_email_backend()

        self.assertIsInstance(backend, SMTPBackend)
        self.assertEqual(backend.host, 'smtp.acme.example.com')
        self.assertEqual(backend.port, 2525)

    @override_settings(EMAIL_WEBHOOK_URL='https://webhook.invalid/test')
    def test_http_webhook_takes_priority_over_organization_smtp(self):
        OrganizationFactory(smtp_host='smtp.acme.example.com')

        backend = get_email_backend()

        self.assertIsInstance(backend, HTTPWebhookBackend)
        self.assertEqual(backend.webhook_url, 'https://webhook.invalid/test')

    @override_settings(
        EMAIL_WEBHOOK_URL='https://generic.invalid/hook',
        POWER_AUTOMATE_WEBHOOK_URL='https://legacy.invalid/hook',
    )
    def test_generic_environment_url_takes_priority_over_legacy_url(self):
        organization = OrganizationFactory(
            smtp_host='smtp.acme.example.com',
            email_delivery_method='http_webhook',
        )
        organization.set_email_webhook_url('https://organization.invalid/hook')
        organization.save()

        backend = get_email_backend(organization)

        self.assertIsInstance(backend, HTTPWebhookBackend)
        self.assertEqual(backend.webhook_url, 'https://generic.invalid/hook')

    @override_settings(
        EMAIL_DELIVERY_METHOD='smtp',
        EMAIL_WEBHOOK_URL='https://generic.invalid/hook',
        POWER_AUTOMATE_WEBHOOK_URL='https://legacy.invalid/hook',
    )
    def test_explicit_smtp_environment_method_overrides_webhook_urls(self):
        organization = OrganizationFactory(
            smtp_host='smtp.acme.example.com',
            email_delivery_method='http_webhook',
        )

        backend = get_email_backend(organization)

        self.assertIsInstance(backend, SMTPBackend)
        self.assertEqual(backend.host, 'smtp.acme.example.com')

    @override_settings(
        EMAIL_DELIVERY_METHOD='',
        EMAIL_WEBHOOK_URL='',
        POWER_AUTOMATE_WEBHOOK_URL='https://legacy.invalid/hook',
    )
    def test_legacy_environment_url_remains_supported(self):
        organization = OrganizationFactory(smtp_host='smtp.acme.example.com')

        backend = get_email_backend(organization)

        self.assertIsInstance(backend, HTTPWebhookBackend)
        self.assertEqual(backend.webhook_url, 'https://legacy.invalid/hook')

    def test_organization_webhook_method_uses_encrypted_url(self):
        organization = OrganizationFactory(email_delivery_method='http_webhook')
        organization.set_email_webhook_url('https://organization.invalid/hook')
        organization.save()

        backend = get_email_backend(organization)

        self.assertIsInstance(backend, HTTPWebhookBackend)
        self.assertEqual(backend.webhook_url, 'https://organization.invalid/hook')

    @override_settings(EMAIL_DELIVERY_METHOD='http_webhook')
    def test_environment_method_uses_organization_webhook_when_url_is_not_overridden(self):
        organization = OrganizationFactory(email_delivery_method='smtp')
        organization.set_email_webhook_url('https://organization.invalid/env-method')
        organization.save()

        backend = get_email_backend(organization)

        self.assertIsInstance(backend, HTTPWebhookBackend)
        self.assertEqual(backend.webhook_url, 'https://organization.invalid/env-method')

    @override_settings(DEFAULT_FROM_EMAIL='fallback@example.com')
    def test_send_email_delivers_through_configured_backend(self):
        OrganizationFactory(smtp_host='', from_email='org@example.com')

        sent = send_email(
            subject='Hello',
            message='Body',
            recipient_list=['someone@example.com'],
        )

        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['someone@example.com'])
        self.assertEqual(mail.outbox[0].from_email, 'org@example.com')


class HTTPWebhookBackendTests(TestCase):
    @patch('core.email_backends.requests.post')
    def test_posts_email_payload_and_counts_successful_message(self, mock_post):
        response = mock_post.return_value
        message = EmailMultiAlternatives(
            subject='Hello',
            body='Plain text',
            from_email='sender@example.com',
            to=['someone@example.com'],
        )
        message.attach_alternative('<p>HTML</p>', 'text/html')
        backend = HTTPWebhookBackend(webhook_url='https://webhook.invalid/test')

        sent = backend.send_messages([message])

        self.assertEqual(sent, 1)
        mock_post.assert_called_once_with(
            'https://webhook.invalid/test',
            json={
                'to': ['someone@example.com'],
                'subject': 'Hello',
                'body': 'Plain text',
                'html_body': '<p>HTML</p>',
                'from_email': 'sender@example.com',
            },
            timeout=10,
        )
        response.raise_for_status.assert_called_once_with()

    @patch('core.email_backends.requests.post')
    def test_logs_request_failure_and_does_not_count_failed_message(self, mock_post):
        import requests

        message = EmailMultiAlternatives(
            subject='Hello',
            body='Plain text',
            from_email='sender@example.com',
            to=['someone@example.com'],
        )
        mock_post.side_effect = requests.RequestException(
            'request failed for https://webhook.invalid/test'
        )
        backend = HTTPWebhookBackend(webhook_url='https://webhook.invalid/test')

        with self.assertLogs('core.email_backends', level='ERROR') as logs:
            sent = backend.send_messages([message])

        self.assertEqual(sent, 0)
        self.assertNotIn('webhook.invalid', ' '.join(logs.output))

    @patch('core.email_backends.requests.post')
    def test_does_not_count_http_error_response(self, mock_post):
        import requests

        message = EmailMultiAlternatives(
            subject='Hello',
            body='Plain text',
            from_email='sender@example.com',
            to=['someone@example.com'],
        )
        mock_post.return_value.raise_for_status.side_effect = requests.HTTPError(
            'server error'
        )
        backend = HTTPWebhookBackend(webhook_url='https://webhook.invalid/test')

        with self.assertLogs('core.email_backends', level='ERROR'):
            sent = backend.send_messages([message])

        self.assertEqual(sent, 0)
        mock_post.return_value.raise_for_status.assert_called_once_with()
