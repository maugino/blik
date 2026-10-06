"""Which Organization fields the environment owns.

Environment variables own matching settings. Some are synchronized into the
organization at startup; delivery-method and webhook variables are runtime
overrides. Letting the admin UI edit environment-owned fields would produce
changes that are ignored or reverted.

So the environment wins, visibly: fields it sets are rendered read-only on the
settings page and rejected server-side if posted anyway. Fields with no env var
(anonymity threshold, registration flags) stay editable in the UI.
"""
import os

# Organization model field -> environment variable that owns it
ENV_MANAGED_FIELDS = {
    'name': 'ORGANIZATION_NAME',
    'email': 'DEFAULT_FROM_EMAIL',
    'from_email': 'DEFAULT_FROM_EMAIL',
    'smtp_host': 'EMAIL_HOST',
    'smtp_port': 'EMAIL_PORT',
    'smtp_username': 'EMAIL_HOST_USER',
    'smtp_password': 'EMAIL_HOST_PASSWORD',
    'smtp_use_tls': 'EMAIL_USE_TLS',
    'email_delivery_method': 'EMAIL_DELIVERY_METHOD',
    'email_webhook_url': 'EMAIL_WEBHOOK_URL',
}


def env_managed_fields():
    """
    Return {field: env_var} for the fields the environment currently owns.

    An env var that is set but empty does not count as owning the field —
    that is how you hand a field back to the UI without editing compose files.
    """
    locked = {
        field: var
        for field, var in ENV_MANAGED_FIELDS.items()
        if os.environ.get(var)
    }
    if not locked.get('email_webhook_url') and os.environ.get('POWER_AUTOMATE_WEBHOOK_URL'):
        locked['email_webhook_url'] = 'POWER_AUTOMATE_WEBHOOK_URL'
    if not locked.get('email_delivery_method'):
        if locked.get('email_webhook_url'):
            locked['email_delivery_method'] = locked['email_webhook_url']
    return locked
