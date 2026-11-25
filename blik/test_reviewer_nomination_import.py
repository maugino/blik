"""Reviewer nomination CSV preview tests.

Previewing is deliberately read-only: it must never create people, cycles,
reviewer tokens, or send invitations.
"""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.factories import UserProfileFactory
from accounts.models import OrgUnitMembership, Reviewee
from accounts.permissions import assign_organization_admin, assign_organization_member
from core.factories import OrganizationFactory, UserFactory
from questionnaires.factories import QuestionnaireFactory
from notifications.models import EmailLog
from reviews.models import ReviewCycle, ReviewerToken


HEADERS = (
    "Participant Name,Participant Email,Rater Name,Rater Email,"
    "Rater Group,Source\n"
)


class ReviewerNominationPreviewTests(TestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.admin = UserFactory(
            username="nomination_admin",
            email="admin@example.com",
        )
        UserProfileFactory(user=self.admin, organization=self.org)
        assign_organization_admin(self.admin)
        self.client.force_login(self.admin)

        self.participant = Reviewee.objects.create(
            organization=self.org,
            name="Participant One",
            email="participant@example.com",
        )
        self.existing_rater = Reviewee.objects.create(
            organization=self.org,
            name="Existing Rater",
            email="existing@example.com",
        )
        self.questionnaire = QuestionnaireFactory(
            organization=self.org,
            is_active=True,
        )
        self.url = reverse("reviewer_nomination_import_preview")

    def upload(self, body, user=None):
        if user is not None:
            self.client.force_login(user)

        file = SimpleUploadedFile(
            "nominations.csv",
            body.encode("utf-8"),
            content_type="text/csv",
        )
        return self.client.post(
            self.url,
            {
                "questionnaire": str(self.questionnaire.pk),
                "file": file,
            },
        )

    def test_valid_csv_previews_existing_and_new_raters(self):
        response = self.upload(
            HEADERS
            + "Participant One,participant@example.com,"
              "Participant One,participant@example.com,Self,Org chart\n"
            + "Participant One,participant@example.com,"
              "Existing Rater,existing@example.com,Manager,Org chart\n"
            + "Participant One,participant@example.com,"
              "New Peer,new.peer@example.com,Peer,\n"
        )

        self.assertEqual(response.status_code, 200)
        preview = response.context["preview"]

        self.assertEqual(preview["stats"]["participants"], 1)
        self.assertEqual(preview["stats"]["assignments"], 3)
        self.assertEqual(preview["stats"]["self"], 1)
        self.assertEqual(preview["stats"]["manager"], 1)
        self.assertEqual(preview["stats"]["peer"], 1)
        self.assertEqual(preview["stats"]["existing_raters"], 2)
        self.assertEqual(preview["stats"]["new_raters"], 1)
        self.assertEqual(preview["errors"], [])

    def test_missing_rater_email_is_rejected(self):
        response = self.upload(
            HEADERS
            + "Participant One,participant@example.com,"
              "Peer Without Email,,Peer,\n"
        )

        self.assertEqual(response.status_code, 200)
        preview = response.context["preview"]

        self.assertTrue(preview["errors"])
        self.assertIn("rater email", " ".join(preview["errors"]).lower())
        self.assertEqual(preview["stats"]["assignments"], 0)

    def test_unknown_participant_is_rejected(self):
        response = self.upload(
            HEADERS
            + "Unknown Person,unknown@example.com,"
              "New Peer,new.peer@example.com,Peer,\n"
        )

        self.assertEqual(response.status_code, 200)
        errors = " ".join(response.context["preview"]["errors"])

        self.assertIn("unknown@example.com", errors)

    def test_preview_changes_nothing(self):
        people_before = Reviewee.objects.count()
        cycles_before = ReviewCycle.objects.count()
        tokens_before = ReviewerToken.objects.count()

        response = self.upload(
            HEADERS
            + "Participant One,participant@example.com,"
              "Participant One,participant@example.com,Self,Org chart\n"
            + "Participant One,participant@example.com,"
              "Brand New Person,new.person@example.com,Peer,\n"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reviewee.objects.count(), people_before)
        self.assertEqual(ReviewCycle.objects.count(), cycles_before)
        self.assertEqual(ReviewerToken.objects.count(), tokens_before)
        self.assertFalse(
            Reviewee.objects.filter(
                organization=self.org,
                email__iexact="new.person@example.com",
            ).exists()
        )

    def preview_for_confirmation(self, body):
        """Run the real preview first so the server creates the pending session state."""
        response = self.upload(body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["preview"]["errors"], [])
        self.assertIn("reviewer_nomination_import", self.client.session)
        return response

    def test_confirm_creates_exact_cycle_and_reviewer_tokens(self):
        body = (
            HEADERS
            + "Participant One,participant@example.com,"
              "Participant One,participant@example.com,Self,Org chart\n"
            + "Participant One,participant@example.com,"
              "Existing Rater,existing@example.com,Manager,Org chart\n"
            + "Participant One,participant@example.com,"
              "New Peer,new.peer@example.com,Peer,\n"
        )
        self.preview_for_confirmation(body)

        response = self.client.post(
            reverse("reviewer_nomination_import_confirm")
        )

        self.assertRedirects(
            response,
            reverse("bulk_send_invitations"),
            fetch_redirect_response=False,
        )

        cycle = ReviewCycle.objects.get(reviewee=self.participant)
        self.assertEqual(cycle.questionnaire, self.questionnaire)

        assignments = sorted(
            cycle.tokens.values_list("category", "reviewer_email")
        )
        self.assertEqual(
            assignments,
            [
                ("manager", "existing@example.com"),
                ("peer", "new.peer@example.com"),
                ("self", "participant@example.com"),
            ],
        )

        self.assertEqual(
            self.client.session["pending_invitation_cycles"],
            [str(cycle.uuid)],
        )
        self.assertEqual(
            self.client.session["pending_bulk_source"],
            "nominations",
        )

    def test_new_rater_is_created_but_not_put_in_org_chart(self):
        body = (
            HEADERS
            + "Participant One,participant@example.com,"
              "Participant One,participant@example.com,Self,Org chart\n"
            + "Participant One,participant@example.com,"
              "New Peer,new.peer@example.com,Peer,\n"
        )
        self.preview_for_confirmation(body)

        self.client.post(reverse("reviewer_nomination_import_confirm"))

        person = Reviewee.objects.get(
            organization=self.org,
            email__iexact="new.peer@example.com",
        )
        self.assertEqual(person.name, "New Peer")
        self.assertTrue(person.is_active)
        self.assertFalse(
            OrgUnitMembership.objects.filter(reviewee=person).exists()
        )

    def test_confirm_queues_no_email(self):
        body = (
            HEADERS
            + "Participant One,participant@example.com,"
              "Participant One,participant@example.com,Self,Org chart\n"
            + "Participant One,participant@example.com,"
              "Existing Rater,existing@example.com,Peer,\n"
        )
        self.preview_for_confirmation(body)

        email_logs_before = EmailLog.objects.count()

        response = self.client.post(
            reverse("reviewer_nomination_import_confirm")
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(EmailLog.objects.count(), email_logs_before)

        cycle = ReviewCycle.objects.get(reviewee=self.participant)
        self.assertFalse(
            cycle.tokens.exclude(invitation_sent_at__isnull=True).exists()
        )

    def test_confirm_creates_one_cycle_per_participant(self):
        participant_two = Reviewee.objects.create(
            organization=self.org,
            name="Participant Two",
            email="participant.two@example.com",
        )

        body = (
            HEADERS
            + "Participant One,participant@example.com,"
              "Participant One,participant@example.com,Self,Org chart\n"
            + "Participant One,participant@example.com,"
              "Existing Rater,existing@example.com,Peer,\n"
            + "Participant Two,participant.two@example.com,"
              "Participant Two,participant.two@example.com,Self,Org chart\n"
            + "Participant Two,participant.two@example.com,"
              "New Peer,new.peer@example.com,Peer,\n"
        )
        self.preview_for_confirmation(body)

        response = self.client.post(
            reverse("reviewer_nomination_import_confirm")
        )

        self.assertEqual(response.status_code, 302)

        cycles = ReviewCycle.objects.filter(
            reviewee__in=[self.participant, participant_two]
        )
        self.assertEqual(cycles.count(), 2)

        cycle_one = cycles.get(reviewee=self.participant)
        cycle_two = cycles.get(reviewee=participant_two)

        self.assertEqual(cycle_one.tokens.count(), 2)
        self.assertEqual(cycle_two.tokens.count(), 2)

    def test_confirm_cannot_be_replayed_from_same_preview(self):
        body = (
            HEADERS
            + "Participant One,participant@example.com,"
              "Participant One,participant@example.com,Self,Org chart\n"
            + "Participant One,participant@example.com,"
              "Existing Rater,existing@example.com,Peer,\n"
        )
        self.preview_for_confirmation(body)

        first = self.client.post(
            reverse("reviewer_nomination_import_confirm")
        )
        self.assertEqual(first.status_code, 302)
        self.assertEqual(
            ReviewCycle.objects.filter(reviewee=self.participant).count(),
            1,
        )

        second = self.client.post(
            reverse("reviewer_nomination_import_confirm")
        )
        self.assertEqual(second.status_code, 302)

        # Confirmation consumes the pending import from the session.
        self.assertEqual(
            ReviewCycle.objects.filter(reviewee=self.participant).count(),
            1,
        )

    def test_non_admin_cannot_preview_nomination_import(self):
        member = UserFactory(
            username="nomination_member",
            email="member@example.com",
        )
        UserProfileFactory(user=member, organization=self.org)
        assign_organization_member(member)

        response = self.upload(
            HEADERS
            + "Participant One,participant@example.com,"
              "New Peer,new.peer@example.com,Peer,\n",
            user=member,
        )

        self.assertEqual(response.status_code, 404)
