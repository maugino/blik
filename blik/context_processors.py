"""
Context processors for making settings available in templates.
"""
from django.conf import settings


def site_settings(request):
    """Expose the configured public site URL to templates."""
    return {'SITE_URL': settings.SITE_URL}


def stripe_settings(request):
    """
    Make Stripe configuration available in templates.
    Used to conditionally show/hide features based on Stripe setup.
    """
    return {
        'STRIPE_PRICE_ID_SAAS': settings.STRIPE_PRICE_ID_SAAS,
        'STRIPE_PRICE_ID_ENTERPRISE': settings.STRIPE_PRICE_ID_ENTERPRISE,
        'HAS_STRIPE_CONFIGURED': bool(settings.STRIPE_PRICE_ID_SAAS or settings.STRIPE_PRICE_ID_ENTERPRISE),
    }
