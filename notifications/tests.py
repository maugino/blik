from unittest.mock import call, patch

from django.conf import settings
from django.test import TestCase, override_settings

from notifications.utils import send_feedback_invitation, send_multiple_invitations
from reviews.factories import ReviewerTokenFactory


@override_settings(DEFAULT_FROM_EMAIL='sender@example.test')
class FeedbackInvitationTests(TestCase):
    @patch('notifications.utils.render_to_string')
    @patch('notifications.utils.send_email', return_value=0)
    def test_sends_rendered_invitation_through_central_email_helper(
        self, mock_send_email, mock_render
    ):
        mock_render.side_effect = ['Plain invitation body', '<p>HTML invitation</p>']
        token = ReviewerTokenFactory()

        result = send_feedback_invitation(token, 'reviewer@example.test')

        self.assertTrue(result)
        self.assertEqual(
            mock_send_email.call_args.kwargs,
            {
                'subject': f'360 Feedback Request for {token.cycle.reviewee.name}',
                'message': 'Plain invitation body',
                'recipient_list': ['reviewer@example.test'],
                'html_message': '<p>HTML invitation</p>',
                'from_email': settings.DEFAULT_FROM_EMAIL,
            },
        )

    @patch('notifications.utils.send_email')
    def test_missing_recipient_returns_false_without_sending(self, mock_send_email):
        result = send_feedback_invitation(ReviewerTokenFactory())

        self.assertFalse(result)
        mock_send_email.assert_not_called()

    @patch('notifications.utils.send_email', side_effect=RuntimeError('send failed'))
    def test_send_exception_propagates(self, mock_send_email):
        with self.assertRaisesRegex(RuntimeError, 'send failed'):
            send_feedback_invitation(ReviewerTokenFactory(), 'reviewer@example.test')

    @patch('notifications.utils.send_feedback_invitation', side_effect=[True, False])
    def test_multiple_invitations_delegate_to_single_invitation_helper(
        self, mock_send_feedback_invitation
    ):
        tokens = [object(), object()]
        emails = ['one@example.test', 'two@example.test']

        results = send_multiple_invitations(tokens, emails)

        self.assertEqual(
            results,
            [
                {'token': tokens[0], 'email': emails[0], 'success': True},
                {'token': tokens[1], 'email': emails[1], 'success': False},
            ],
        )
        self.assertEqual(
            mock_send_feedback_invitation.call_args_list,
            [call(tokens[0], emails[0]), call(tokens[1], emails[1])],
        )
