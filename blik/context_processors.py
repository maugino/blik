"""
Context processors for making settings available in templates.
"""
from pathlib import Path

from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse

from core.branding import organization_logo_urls


def stripe_settings(request):
    """
    Make Stripe configuration available in templates.
    Used to conditionally show/hide features based on Stripe setup.
    """
    return {
        'STRIPE_PRICE_ID_SAAS': settings.STRIPE_PRICE_ID_SAAS,
        'STRIPE_PRICE_ID_ENTERPRISE': settings.STRIPE_PRICE_ID_ENTERPRISE,
        'HAS_STRIPE_CONFIGURED': bool(
            settings.STRIPE_PRICE_ID_SAAS
            or settings.STRIPE_PRICE_ID_ENTERPRISE
            or settings.STRIPE_PRICE_ID_SINGLE
        ),
    }


def billing(request):
    """The billing nav link, and a banner while the subscription needs the admin's action."""
    from subscriptions.models import Subscription
    from subscriptions.utils import can_see_billing, entitlement

    user = getattr(request, 'user', None)
    organization = getattr(request, 'organization', None)
    # ponytail: a few small queries on every dashboard page; cache per request if it ever shows up in profiles
    if not (user and user.is_authenticated and can_see_billing(organization, user)):
        return {}
    unpaid = Subscription.objects.filter(organization=organization, status__in=('past_due', 'unpaid')).exists()
    return {
        'show_billing': True,
        # A failed payment also counts as lapsed, so check it first: Stripe is still retrying.
        'billing_problem': 'unpaid' if unpaid else 'lapsed' if entitlement(organization) == 'lapsed' else None,
    }



def sender_identity(request):
    """The names a user must give before an invitation goes out: see accounts/sender_identity.py."""
    from accounts.sender_identity import missing

    user = getattr(request, 'user', None)
    organization = getattr(request, 'organization', None)
    if not organization or user is None or not user.is_authenticated:
        return {}
    return {'sender_identity_missing': missing(user, organization)}


def branding(request):
    """Resolve organization branding with deployment assets as fallback."""
    organization = getattr(request, 'organization', None)
    light, dark = organization_logo_urls(organization)

    if light == 'light':
        light = reverse(
            'organization_brand_logo',
            kwargs={'theme': 'light'},
        )

    if dark == 'dark':
        dark = reverse(
            'organization_brand_logo',
            kwargs={'theme': 'dark'},
        )
    elif dark == 'light':
        dark = light

    # Existing deployment-specific Enovis assets remain a backwards-compatible
    # fallback. They are intentionally ignored by Git and may not exist.
    static_img = Path(settings.BASE_DIR) / 'static' / 'img' / 'logos'
    deployment_light = static_img / 'enovis-logo-color.svg'
    deployment_dark = static_img / 'enovis-logo-white.svg'

    if not light and deployment_light.is_file():
        light = static('img/logos/enovis-logo-color.svg')

    if not dark:
        if deployment_dark.is_file():
            dark = static('img/logos/enovis-logo-white.svg')
        else:
            dark = light

    return {
        'cobranding_enabled': bool(light),
        'cobrand_logo_light': light,
        'cobrand_logo_dark': dark or light,
    }
