from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from django.urls import reverse
from django_ratelimit.decorators import ratelimit
from .models import ReviewerToken, Response, ReviewCycle
from questionnaires.models import Question
from questionnaires.translations import (
    available_questionnaire_language_options,
    questionnaire_language_name,
    resolve_questionnaire_language,
)
import secrets
import logging

logger = logging.getLogger(__name__)


def claim_token(request, invitation_token):
    """
    Claim an available token using a secure invitation token.
    First shows a page that checks localStorage, then randomly assigns if needed.
    """
    # Find the cycle and category by invitation token
    cycle = None
    category = None

    # Try each category token field
    for cat_code, cat_display in ReviewerToken.CATEGORY_CHOICES:
        field_name = f'invitation_token_{cat_code}'
        cycles = ReviewCycle.objects.filter(**{field_name: invitation_token, 'status': 'active'})
        if cycles.exists():
            cycle = cycles.first()
            category = cat_code
            break

    if not cycle or not category:
        return render(request, 'reviews/claim_error.html', {
            'error': 'Invalid or expired invitation link.'
        }, status=404)

    # If coming from redirect page (has force_claim param), skip localStorage check
    if request.GET.get('force_claim'):
        # Get available tokens (not claimed, not completed, and NOT assigned to an email)
        # This prevents invite links from claiming tokens meant for specific email invitations
        available_tokens = list(
            ReviewerToken.objects.filter(
                cycle=cycle,
                category=category,
                claimed_at__isnull=True,
                completed_at__isnull=True,
                reviewer_email__isnull=True  # Only claim tokens without email assignments
            )
        )

        if not available_tokens:
            # No available tokens - create a new one dynamically
            token = ReviewerToken.objects.create(
                cycle=cycle,
                category=category,
                claimed_at=timezone.now()
            )
        else:
            # Cryptographically randomly select a token from available ones
            token = secrets.choice(available_tokens)
            # Mark as claimed immediately
            token.claimed_at = timezone.now()
            token.save()

        # Redirect to feedback form
        return redirect('reviews:feedback_form', token=token.token)

    # Show redirect page that checks localStorage first
    return render(request, 'reviews/claim_redirect.html', {
        'invitation_token': str(invitation_token),
        'category': category,
    })


def feedback_form(request, token):
    """Token-based feedback form view"""
    reviewer_token = get_object_or_404(
        ReviewerToken.objects.select_related(
            'cycle__questionnaire',
            'cycle__reviewee',
        ).prefetch_related(
            'cycle__questionnaire__translations',
            'cycle__questionnaire__sections__translations',
            'cycle__questionnaire__sections__questions__translations',
        ),
        token=token,
    )

    # Check if already completed
    if reviewer_token.is_completed:
        return render(request, 'reviews/feedback_complete.html', {
            'token': reviewer_token,
            'cycle': reviewer_token.cycle,
        })

    cycle = reviewer_token.cycle

    # Check if the cycle is closed/completed
    if cycle.status == 'completed':
        return render(request, 'reviews/claim_error.html', {
            'error': 'This review cycle has been closed. Feedback can no longer be submitted.'
        }, status=410)

    # Mark token as claimed on first access (for email-invited users)
    if reviewer_token.claimed_at is None:
        reviewer_token.claimed_at = timezone.now()
        reviewer_token.save(update_fields=['claimed_at'])

    questionnaire = cycle.questionnaire
    language_options = available_questionnaire_language_options(questionnaire)
    selected_language = resolve_questionnaire_language(
        questionnaire,
        request.GET.get('lang'),
    )

    # Get all sections with questions
    sections = questionnaire.sections.all()
    questionnaire_display_name = questionnaire.resolve_name(selected_language)
    questionnaire_display_description = questionnaire.resolve_description(selected_language)
    for section in sections:
        section.display_title = section.resolve_title(selected_language)
        section.display_description = section.resolve_description(selected_language)
        for question in section.questions.all():
            question.display_text = question.resolve_question_text(selected_language)
            question.display_options = question.get_display_options(selected_language)
            question.display_config = question.resolve_config(selected_language)

    # Get existing responses for this token
    existing_responses = {}
    if request.method == 'GET':
        responses = Response.objects.filter(token=reviewer_token).select_related('question')
        existing_responses = {str(r.question.id): r.answer_data.get('value') for r in responses}

    # Get invitation token for localStorage key
    invitation_token = cycle.get_invitation_token(reviewer_token.category)

    context = {
        'token': reviewer_token,
        'cycle': cycle,
        'questionnaire': questionnaire,
        'questionnaire_display_name': questionnaire_display_name,
        'questionnaire_display_description': questionnaire_display_description,
        'language_options': language_options,
        'selected_language': selected_language,
        'selected_language_name': questionnaire_language_name(selected_language),
        'sections': sections,
        'reviewee': cycle.reviewee,
        'existing_responses': existing_responses,
        'invitation_token': invitation_token,
    }

    return render(request, 'reviews/feedback_form.html', context)


@require_http_methods(["POST"])
@ratelimit(key='ip', rate='10/h', method='POST', block=True)
def submit_feedback(request, token):
    """Handle feedback form submission"""
    reviewer_token = get_object_or_404(
        ReviewerToken.objects.select_related('cycle__questionnaire'),
        token=token,
    )

    # Check if already completed
    if reviewer_token.is_completed:
        return JsonResponse({'error': 'Feedback already submitted'}, status=400)

    cycle = reviewer_token.cycle

    # Check if the cycle is closed/completed
    if cycle.status == 'completed':
        return JsonResponse({'error': 'This review cycle has been closed. Feedback can no longer be submitted.'}, status=410)

    questionnaire = cycle.questionnaire
    selected_language = resolve_questionnaire_language(
        questionnaire,
        request.POST.get('lang', request.GET.get('lang')),
    )

    # Get all questions for validation
    questions = Question.objects.filter(section__questionnaire=questionnaire)

    errors = []
    responses_to_save = []

    # Validate and prepare responses
    for question in questions:
        field_name = f'question_{question.id}'

        # Handle multiple_choice differently (get list of values)
        if question.question_type == 'multiple_choice':
            answer_values = request.POST.getlist(field_name)
            # Filter out empty strings
            answer_values = [v.strip() for v in answer_values if v.strip()]

            # Check required fields
            if question.required and not answer_values:
                errors.append(f'Question "{question.question_text[:50]}" is required')
                continue

            # Skip empty optional fields
            if not answer_values:
                continue

            canonical_choices = (question.config or {}).get('choices', [])
            if (
                not isinstance(canonical_choices, list)
                or any(not isinstance(value, str) for value in canonical_choices)
                or len(answer_values) != len(set(answer_values))
                or any(value not in canonical_choices for value in answer_values)
            ):
                errors.append(f'Invalid choice for question "{question.question_text[:50]}"')
                continue

            answer_data = {'value': answer_values}
        else:
            # For all other question types (single value)
            raw_answer_value = request.POST.get(field_name, '')
            answer_value = raw_answer_value.strip()

            # Check required fields
            if question.required and not answer_value:
                errors.append(f'Question "{question.question_text[:50]}" is required')
                continue

            # Skip empty optional fields
            if not answer_value:
                continue

            # Validate based on question type
            if question.question_type == 'rating':
                try:
                    rating = int(answer_value)
                    min_val = int((question.config or {}).get('min', 1))
                    max_val = int((question.config or {}).get('max', 5))
                    if rating < min_val or rating > max_val:
                        errors.append(f'Rating must be between {min_val} and {max_val}')
                        continue
                    answer_data = {'value': rating}
                except (TypeError, ValueError):
                    errors.append('Invalid rating value')
                    continue
            elif question.question_type == 'scale':
                try:
                    scale_value = int(answer_value)
                    config = question.config or {}
                    min_val = int(config.get('min', 1))
                    max_val = int(config.get('max', 100))
                    step = int(config.get('step', 1))
                    if (
                        step <= 0
                        or scale_value < min_val
                        or scale_value > max_val
                        or (scale_value - min_val) % step
                    ):
                        errors.append(f'Scale value must be between {min_val} and {max_val}')
                        continue
                    answer_data = {'value': scale_value}
                except (TypeError, ValueError):
                    errors.append('Invalid scale value')
                    continue
            elif question.question_type in {'single_choice', 'likert'}:
                config = question.config or {}
                option_key = 'scale' if question.question_type == 'likert' else 'choices'
                canonical_options = config.get(option_key, [])
                if (
                    not isinstance(canonical_options, list)
                    or any(not isinstance(value, str) for value in canonical_options)
                    or answer_value not in canonical_options
                ):
                    errors.append(f'Invalid choice for question "{question.question_text[:50]}"')
                    continue
                answer_data = {'value': answer_value}
            elif question.question_type == 'text':
                if not raw_answer_value.strip():
                    continue
                answer_data = {'value': raw_answer_value}
            else:
                errors.append(f'Unsupported question type for question "{question.question_text[:50]}"')
                continue

        responses_to_save.append({
            'cycle': cycle,
            'question': question,
            'token': reviewer_token,
            'category': reviewer_token.category,
            'answer_data': answer_data,
        })

    if errors:
        return JsonResponse({
            'errors': errors,
            'language': selected_language,
        }, status=400)

    # Save all responses in a transaction
    try:
        with transaction.atomic():
            # Delete existing responses for this token
            Response.objects.filter(token=reviewer_token).delete()

            # Create new responses
            for response_data in responses_to_save:
                Response.objects.create(**response_data)

            # Mark token as completed
            reviewer_token.completed_at = timezone.now()
            reviewer_token.save()

            # Send feedback.submitted webhook
            from api.webhooks import send_webhook
            send_webhook(
                organization=cycle.reviewee.organization,
                event_type="feedback.submitted",
                payload={
                    "cycle_id": str(cycle.uuid),
                    "category": reviewer_token.category,
                    "submitted_at": reviewer_token.completed_at.isoformat(),
                },
            )

            # Check if all tokens are completed
            # Only auto-close when every token has a reviewer_email (email-assigned cycle).
            # Invite-link cycles (tokens without emails) stay open for new reviewers.
            all_tokens = cycle.tokens.all()
            has_open_invite = all_tokens.filter(reviewer_email__isnull=True).exists()
            all_tokens_completed = (
                not has_open_invite
                and not all_tokens.filter(completed_at__isnull=True).exists()
            )

            if all_tokens_completed and cycle.status == 'active':
                # Auto-close the cycle
                cycle.status = 'completed'
                cycle.save()

                # Auto-generate report
                from reports.services import generate_report, send_report_ready_notification
                try:
                    report = generate_report(cycle)

                    # Send notification email if organization setting enabled
                    organization = cycle.reviewee.organization
                    if organization and organization.auto_send_report_email:
                        email_stats = send_report_ready_notification(report)
                        if email_stats.get('errors'):
                            print(f"Errors sending report email for cycle {cycle.id}: {email_stats['errors']}")
                except Exception as e:
                    # Log error but don't fail the submission
                    print(f"Error auto-generating report for cycle {cycle.id}: {e}")

        completion_url = reverse('reviews:feedback_complete', kwargs={'token': token})
        return JsonResponse({
            'success': True,
            'redirect': f'{completion_url}?lang={selected_language}',
        })

    except Exception as e:
        logger.exception('Error submitting feedback')
        return JsonResponse({'error': 'Something went wrong. Please try again.'}, status=500)


def feedback_complete(request, token):
    """Confirmation page after feedback submission"""
    reviewer_token = get_object_or_404(ReviewerToken, token=token)

    if not reviewer_token.is_completed:
        return redirect('feedback_form', token=token)

    return render(request, 'reviews/feedback_complete.html', {
        'token': reviewer_token,
        'cycle': reviewer_token.cycle,
    })
