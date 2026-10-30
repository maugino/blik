from core.email import send_email
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import gettext as _
from core.url import get_absolute_url
from reviews.models import ReviewerToken
from reviews.services import token_language


def send_feedback_invitation(token, reviewer_email=None):
    """Send feedback invitation email for a reviewer token"""

    full_url = get_absolute_url('reviews:feedback_form', token.token)

    with translation.override(token_language(token)):
        context = {
            'reviewee_name': token.cycle.reviewee.name,
            'category': token.get_category_display(),
            'feedback_url': full_url,
            'token': token,
        }

        subject = _('360 Feedback Request for %(name)s') % {'name': token.cycle.reviewee.name}

        # Render text email
        message = render_to_string('notifications/feedback_invitation.txt', context)

        # Render HTML email
        html_message = render_to_string('notifications/feedback_invitation.html', context)

    # Send email
    if reviewer_email:
        send_email(
            subject=subject,
            message=message,
            recipient_list=[reviewer_email],
            html_message=html_message,
        )
        return True

    return False


def send_multiple_invitations(tokens, emails):
    """Send invitations for multiple tokens with corresponding emails"""
    if len(tokens) != len(emails):
        raise ValueError("Number of tokens must match number of emails")

    results = []
    for token, email in zip(tokens, emails):
        try:
            success = send_feedback_invitation(token, email)
            results.append({'token': token, 'email': email, 'success': success})
        except Exception as e:
            results.append({'token': token, 'email': email, 'success': False, 'error': str(e)})

    return results
