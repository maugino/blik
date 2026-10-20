import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_teams_notification(
    subject,
    message,
    recipient_list,
    html_message=None,
    from_email=None,
    action_url=None,
    peer_url=None,
    manager_url=None,
    direct_report_url=None,
):
    """Send a notification to Teams through Power Automate."""

    webhook_url = getattr(settings, "POWER_AUTOMATE_WEBHOOK_URL", None)

    if not webhook_url:
        return False

    payload = {
        "to": recipient_list,
        "subject": subject,
        "body": message,
        "html_body": html_message or message,
        "from_email": from_email or settings.DEFAULT_FROM_EMAIL,
        "action_url": action_url or "",
        "peer_url": peer_url or "",
        "manager_url": manager_url or "",
        "direct_report_url": direct_report_url or "",
    }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        logger.exception("Failed to send Teams notification")
        return False
