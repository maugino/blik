from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.contrib.auth.models import User

from accounts.models import Reviewee, UserProfile
from core.models import Organization
from questionnaires.models import (
    Questionnaire,
    QuestionnaireTranslation,
    Question,
    QuestionSection,
    QuestionSectionTranslation,
    QuestionTranslation,
)
from reviews.models import Response, ReviewCycle, ReviewerToken


class RespondentQuestionnaireLanguageTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='Respondent language organization',
            email='respondents@example.test',
        )
        self.questionnaire = Questionnaire.objects.create(
            organization=self.organization,
            name='Canonical questionnaire',
            description='Canonical description',
            source_language='en-us',
        )
        self.section = QuestionSection.objects.create(
            questionnaire=self.questionnaire,
            title='Canonical section',
            description='Canonical section description',
            order=0,
        )
        self.rating = Question.objects.create(
            section=self.section,
            question_type='rating',
            question_text='Canonical rating question',
            config={'min': 1, 'max': 2, 'labels': {'1': 'Poor', '2': 'Good'}},
            required=False,
            order=0,
        )
        self.likert = Question.objects.create(
            section=self.section,
            question_type='likert',
            question_text='Canonical Likert question',
            config={'scale': ['Often', 'Always']},
            required=False,
            order=1,
        )
        self.single_choice = Question.objects.create(
            section=self.section,
            question_type='single_choice',
            question_text='Canonical single choice question',
            config={'choices': ['Yes', 'No']},
            required=False,
            order=2,
        )
        self.multiple_choice = Question.objects.create(
            section=self.section,
            question_type='multiple_choice',
            question_text='Canonical multiple choice question',
            config={'choices': ['A', 'B']},
            required=False,
            order=3,
        )
        self.scale = Question.objects.create(
            section=self.section,
            question_type='scale',
            question_text='Canonical scale question',
            config={
                'min': 1,
                'max': 9,
                'step': 2,
                'min_label': 'Not at all',
                'max_label': 'Extremely',
            },
            required=False,
            order=4,
        )
        self.text = Question.objects.create(
            section=self.section,
            question_type='text',
            question_text='Canonical text question',
            config={},
            required=False,
            order=5,
        )
        self.reviewee = Reviewee.objects.create(
            organization=self.organization,
            name='Reviewed Person',
            email='reviewee@example.test',
        )
        self.user = User.objects.create_user(
            username='respondent-test-owner',
            email='owner@example.test',
            password='test-password',
        )
        UserProfile.objects.create(
            user=self.user,
            organization=self.organization,
        )
        self.cycle = ReviewCycle.objects.create(
            reviewee=self.reviewee,
            questionnaire=self.questionnaire,
            created_by=self.user,
        )
        self.token = ReviewerToken.objects.create(
            cycle=self.cycle,
            category='peer',
        )
        self.form_url = reverse(
            'reviews:feedback_form',
            kwargs={'token': self.token.token},
        )
        self.submit_url = reverse(
            'reviews:submit_feedback',
            kwargs={'token': self.token.token},
        )

    def add_french_translations(self):
        QuestionnaireTranslation.objects.create(
            questionnaire=self.questionnaire,
            language_code='fr',
            name='Questionnaire traduit',
            description='Description traduite',
        )
        QuestionSectionTranslation.objects.create(
            section=self.section,
            language_code='fr',
            title='Section traduite',
            description='Description de section traduite',
        )
        QuestionTranslation.objects.create(
            question=self.rating,
            language_code='fr',
            question_text='Question de notation',
            translated_config={'labels': {'1': 'Faible'}},
        )
        QuestionTranslation.objects.create(
            question=self.likert,
            language_code='fr',
            question_text='Question Likert',
            translated_config={'scale': ['Souvent', 'Toujours']},
        )
        QuestionTranslation.objects.create(
            question=self.single_choice,
            language_code='fr',
            question_text='Question à choix unique',
            translated_config={'choices': ['Oui', 'Non']},
        )
        QuestionTranslation.objects.create(
            question=self.multiple_choice,
            language_code='fr',
            question_text='Question à choix multiples',
            translated_config={'choices': ['Un', 'Deux']},
        )
        QuestionTranslation.objects.create(
            question=self.scale,
            language_code='fr',
            question_text='Question à échelle',
            translated_config={
                'min_label': 'Pas du tout',
                'max_label': 'Extrêmement',
            },
        )
        QuestionTranslation.objects.create(
            question=self.text,
            language_code='fr',
            question_text='Question ouverte',
        )

    def test_language_selector_offers_only_source_and_added_supported_languages(self):
        QuestionnaireTranslation.objects.create(
            questionnaire=self.questionnaire,
            language_code='fr',
        )
        QuestionnaireTranslation.objects.create(
            questionnaire=self.questionnaire,
            language_code='zz',
        )

        response = self.client.get(self.form_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_language'], 'en-us')
        self.assertEqual(
            response.context['language_options'],
            [
                {'code': 'en-us', 'label': 'English'},
                {'code': 'fr', 'label': 'French'},
            ],
        )
        self.assertContains(response, 'Questionnaire language')
        self.assertContains(response, 'English')
        self.assertContains(response, 'French')
        self.assertNotContains(response, 'Simplified Chinese')
        self.assertNotContains(response, 'zz')

    def test_available_partial_translation_can_be_selected_and_content_falls_back(self):
        QuestionnaireTranslation.objects.create(
            questionnaire=self.questionnaire,
            language_code='fr',
            name='Questionnaire traduit',
            description='',
        )
        QuestionSectionTranslation.objects.create(
            section=self.section,
            language_code='fr',
            title='Section traduite',
            description='',
        )
        QuestionTranslation.objects.create(
            question=self.likert,
            language_code='fr',
            question_text='',
            translated_config={'scale': ['Souvent', '']},
        )

        response = self.client.get(f'{self.form_url}?lang=FR')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_language'], 'fr')
        self.assertContains(response, 'Questionnaire traduit')
        self.assertContains(response, 'Canonical description')
        self.assertContains(response, 'Section traduite')
        self.assertContains(response, 'Canonical section description')
        self.assertContains(response, 'Canonical rating question')
        self.assertContains(response, 'Canonical Likert question')
        self.assertContains(response, 'value="Often"')
        self.assertContains(response, 'Souvent')
        self.assertContains(response, 'Always')

    def test_invalid_unsupported_unavailable_and_malformed_languages_fall_back_to_source(self):
        QuestionnaireTranslation.objects.create(
            questionnaire=self.questionnaire,
            language_code='fr',
            name='Nom français',
        )

        for requested_language in ('not a language', 'zz', 'de', 'fr-fr'):
            with self.subTest(language=requested_language):
                response = self.client.get(
                    self.form_url,
                    {'lang': requested_language},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['selected_language'], 'en-us')
                self.assertContains(response, 'Canonical questionnaire')

    def test_french_rendering_translates_all_content_but_keeps_input_values_canonical(self):
        self.add_french_translations()

        response = self.client.get(f'{self.form_url}?lang=fr')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_language_name'], 'French')
        self.assertContains(response, 'Questionnaire traduit')
        self.assertContains(response, 'Description traduite')
        self.assertContains(response, 'Section traduite')
        self.assertContains(response, 'Description de section traduite')
        self.assertContains(response, 'Question de notation')
        self.assertContains(response, 'Faible')
        self.assertContains(response, 'Good')
        self.assertContains(response, 'Question Likert')
        self.assertContains(response, 'value="Often"')
        self.assertContains(response, 'value="Always"')
        self.assertContains(response, 'Souvent')
        self.assertContains(response, 'Toujours')
        self.assertContains(response, 'value="Yes"')
        self.assertContains(response, 'value="No"')
        self.assertContains(response, 'Oui')
        self.assertContains(response, 'Non')
        self.assertContains(response, 'value="A"')
        self.assertContains(response, 'value="B"')
        self.assertContains(response, 'Un')
        self.assertContains(response, 'Deux')
        self.assertContains(response, 'Pas du tout')
        self.assertContains(response, 'Extrêmement')
        self.assertContains(response, 'min="1"')
        self.assertContains(response, 'max="9"')
        self.assertContains(response, 'step="2"')
        self.assertContains(response, 'Question ouverte')

    def _valid_submission(self):
        return {
            'lang': 'fr',
            f'question_{self.rating.id}': '2',
            f'question_{self.likert.id}': 'Often',
            f'question_{self.single_choice.id}': 'Yes',
            f'question_{self.multiple_choice.id}': ['A', 'B'],
            f'question_{self.scale.id}': '5',
            f'question_{self.text.id}': '  Free text, unchanged.  ',
        }

    @patch('api.webhooks.send_webhook')
    def test_submission_stores_canonical_values_and_preserves_language_redirect(self, _send_webhook):
        self.add_french_translations()

        response = self.client.post(self.submit_url, self._valid_submission())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(response.json()['redirect'].endswith('?lang=fr'))
        stored = {
            item.question_id: item.answer_data['value']
            for item in Response.objects.filter(token=self.token)
        }
        self.assertEqual(stored[self.rating.id], 2)
        self.assertEqual(stored[self.likert.id], 'Often')
        self.assertEqual(stored[self.single_choice.id], 'Yes')
        self.assertEqual(stored[self.multiple_choice.id], ['A', 'B'])
        self.assertEqual(stored[self.scale.id], 5)
        self.assertEqual(stored[self.text.id], '  Free text, unchanged.  ')

    def test_noncanonical_labels_and_invalid_numeric_values_are_rejected(self):
        self.add_french_translations()
        invalid_values = [
            (f'question_{self.likert.id}', 'Souvent'),
            (f'question_{self.single_choice.id}', 'Oui'),
            (f'question_{self.multiple_choice.id}', ['Un', 'B']),
            (f'question_{self.rating.id}', '3'),
            (f'question_{self.scale.id}', '4'),
            (f'question_{self.scale.id}', '11'),
        ]

        for index, (field_name, invalid_value) in enumerate(invalid_values, start=1):
            with self.subTest(field=field_name, value=invalid_value):
                response = self.client.post(
                    self.submit_url,
                    {**self._valid_submission(), field_name: invalid_value},
                    REMOTE_ADDR=f'192.0.2.{index}',
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['language'], 'fr')
                self.assertFalse(Response.objects.filter(token=self.token).exists())

    def test_invalid_token_stays_invalid_with_language_parameter(self):
        missing_token_url = reverse(
            'reviews:feedback_form',
            kwargs={'token': '00000000-0000-0000-0000-000000000001'},
        )

        response = self.client.get(f'{missing_token_url}?lang=fr')

        self.assertEqual(response.status_code, 404)

    def test_translation_rows_are_prefetched_without_per_question_queries(self):
        self.add_french_translations()

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(f'{self.form_url}?lang=fr')

        self.assertEqual(response.status_code, 200)
        sql = [query['sql'].lower() for query in queries]
        for table in (
            'questionnairetranslation',
            'questionsectiontranslation',
            'questiontranslation',
        ):
            self.assertLessEqual(
                sum(table in query for query in sql),
                1,
                f'{table} was queried more than once',
            )
