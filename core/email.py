"""Central email utilities that select organization and environment backends."""
import logging

from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.mail.backends.smtp import EmailBackend
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from .models import Organization
from .email_backends import HTTPWebhookBackend

logger = logging.getLogger(__name__)


def _environment_webhook_url():
    """Get the preferred generic URL, falling back to the legacy variable."""
    return (
        getattr(settings, 'EMAIL_WEBHOOK_URL', '')
        or getattr(settings, 'POWER_AUTOMATE_WEBHOOK_URL', '')
    )


def _email_delivery_method(organization):
    """Resolve the selected method, keeping environment overrides secret-free."""
    environment_method = getattr(settings, 'EMAIL_DELIVERY_METHOD', '').strip().lower()
    if environment_method:
        if environment_method not in {'smtp', 'http_webhook'}:
            raise ImproperlyConfigured(
                'EMAIL_DELIVERY_METHOD must be "smtp" or "http_webhook"'
            )
        return environment_method

    if _environment_webhook_url():
        return 'http_webhook'
    return getattr(organization, 'email_delivery_method', 'smtp')


def get_email_delivery_method(organization=None):
    """Return the effective delivery method without exposing webhook secrets."""
    if organization is None:
        try:
            organization = Organization.objects.filter(is_active=True).first()
        except Exception:
            logger.exception('Error loading organization email settings')
    return _email_delivery_method(organization)


def email_webhook_is_configured(organization=None):
    """Return whether any effective webhook URL is configured, without decrypting it."""
    if _environment_webhook_url():
        return True
    return bool(organization and organization.email_webhook_url_encrypted)


def get_email_backend(organization=None):
    """
    Select the organization or environment-configured email backend.
    SMTP falls back to Django's configured backend when no organization host
    is configured, preserving console and locmem behavior.
    """
    try:
        org = organization or Organization.objects.filter(is_active=True).first()
    except Exception:
        logger.exception('Error loading organization email settings')
        org = None

    if _email_delivery_method(org) == 'http_webhook':
        webhook_url = _environment_webhook_url()
        if not webhook_url and org:
            webhook_url = org.get_email_webhook_url()
        return HTTPWebhookBackend(webhook_url=webhook_url)

    try:
        if org and org.smtp_host:
            # Use organization's SMTP settings
            return EmailBackend(
                host=org.smtp_host,
                port=org.smtp_port,
                username=org.smtp_username,
                password=org.smtp_password,
                use_tls=org.smtp_use_tls,
                fail_silently=False,
            )
    except Exception:
        logger.exception('Error loading organization email settings')

    return get_connection(fail_silently=False)


def get_from_email(organization=None):
    """Get the from_email from Organization or fall back to Django settings"""
    try:
        org = organization or Organization.objects.filter(is_active=True).first()
        if org and org.from_email:
            return org.from_email
    except Exception:
        pass

    return settings.DEFAULT_FROM_EMAIL


def send_email(
    subject, message, recipient_list, html_message=None, from_email=None, organization=None
):
    """
    Send email through the organization's effective delivery configuration.

    Args:
        subject: Email subject
        message: Plain text message
        recipient_list: List of recipient email addresses
        html_message: Optional HTML version of message
        from_email: Optional from email (defaults to organization setting)
        organization: Optional Organization for selecting organization-specific settings

    Returns:
        Number of emails sent (0 or 1)
    """
    if from_email is None:
        from_email = get_from_email(organization)

    backend = get_email_backend(organization)

    email = EmailMultiAlternatives(
        subject=subject,
        body=message,
        from_email=from_email,
        to=recipient_list,
        connection=backend,
    )

    if html_message:
        email.attach_alternative(html_message, 'text/html')

    return email.send()


def send_password_reset_email(user, token):
    """
    Send password reset email to user.

    Args:
        user: User object
        token: PasswordResetToken object

    Returns:
        Number of emails sent (0 or 1)
    """
    from django.template.loader import render_to_string
    from django.urls import reverse

    # Build reset URL
    reset_url = f'{settings.SITE_PROTOCOL}://{settings.SITE_DOMAIN}{reverse("reset_password", args=[token.token])}'

    subject = f'Reset your {settings.SITE_NAME} password'

    context = {
        'user': user,
        'reset_url': reset_url,
        'site_name': settings.SITE_NAME,
    }

    html_message = render_to_string('emails/password_reset.html', context)
    text_message = render_to_string('emails/password_reset.txt', context)
    from accounts.models import UserProfile
    profile = UserProfile.objects.filter(user=user).select_related('organization').first()

    return send_email(
        subject=subject,
        message=text_message,
        recipient_list=[user.email],
        html_message=html_message,
        organization=profile.organization if profile else None,
    )


def send_welcome_email(user, organization, password=None):
    """
    Send welcome email to newly registered user.

    Args:
        user: User object
        organization: Organization object
        password: Optional password to include in email (for admin-created accounts)

    Returns:
        Number of emails sent (0 or 1)
    """
    import random
    from django.template.loader import render_to_string
    from django.urls import reverse
    from .models import WelcomeEmailFact

    # Build login URL
    login_url = f'{settings.SITE_PROTOCOL}://{settings.SITE_DOMAIN}{reverse("login")}'

    # Build Dreyfus model URL
    dreyfus_url = f'{settings.SITE_PROTOCOL}://{settings.SITE_DOMAIN}/landing/dreyfus-model/'

    # Get active facts from database
    active_facts = list(WelcomeEmailFact.objects.filter(is_active=True))

    if active_facts:
        # Select a random fact from the database
        selected_fact_obj = random.choice(active_facts)
        selected_fact = {
            'title': selected_fact_obj.title,
            'content': selected_fact_obj.content
        }
    else:
        # Fallback if no facts in database
        selected_fact = {
            'title': 'The Power of 360 Feedback',
            'content': 'Research shows that <strong>360-degree feedback increases self-awareness by up to 30%</strong> and significantly improves leadership effectiveness.'
        }

    # Use different templates based on whether password is provided
    if password:
        # Admin-created account with credentials
        subject = f'Welcome to {settings.SITE_NAME} - Your Account is Ready'
        html_template = 'emails/welcome.html'
        text_template = 'emails/welcome.txt'
    else:
        # Invited member (already set their own password)
        subject = f'Welcome to {organization.name}!'
        html_template = 'emails/welcome_member.html'
        text_template = 'emails/welcome_member.txt'

    # Render email templates
    context = {
        'organization': organization,
        'user': user,
        'password': password,
        'login_url': login_url,
        'dreyfus_url': dreyfus_url,
        'site_name': settings.SITE_NAME,
        'fact_title': selected_fact['title'],
        'fact_content': selected_fact['content'],
    }

    html_message = render_to_string(html_template, context)
    text_message = render_to_string(text_template, context)

    return send_email(
        subject=subject,
        message=text_message,
        recipient_list=[user.email],
        html_message=html_message,
        from_email=organization.from_email if organization.from_email else None,
        organization=organization,
    )
