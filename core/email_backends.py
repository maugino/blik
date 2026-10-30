"""Custom Django email backends."""

import logging

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class PowerAutomateBackend(BaseEmailBackend):
    """Send email messages to a Power Automate HTTP webhook."""

    def __init__(self, webhook_url=None, fail_silently=False):
        super().__init__(fail_silently=fail_silently)
        self.webhook_url = webhook_url or getattr(
            settings, 'POWER_AUTOMATE_WEBHOOK_URL', ''
        )

    def send_messages(self, email_messages):
        sent_count = 0

        for message in email_messages:
            html_body = next(
                (
                    content
                    for content, mimetype in getattr(message, 'alternatives', [])
                    if mimetype == 'text/html'
                ),
                None,
            )
            payload = {
                'to': list(message.to),
                'subject': message.subject,
                'body': message.body,
                'html_body': html_body,
                'from_email': message.from_email,
            }

            try:
                response = requests.post(self.webhook_url, json=payload)
                response.raise_for_status()
            except requests.RequestException:
                logger.exception('Failed to send email via Power Automate webhook')
                continue

            sent_count += 1

        return sent_count
