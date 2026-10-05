import json
from copy import deepcopy

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.urls import resolve

from accounts.factories import UserProfileFactory
from core.factories import OrganizationFactory
from questionnaires.factories import (
    QuestionnaireFactory,
    QuestionFactory,
    QuestionSectionFactory,
)
from questionnaires.models import (
    Question,
    Questionnaire,
    QuestionnaireTranslation,
    QuestionSectionTranslation,
    QuestionTranslation,
)
from core.languages import SUPPORTED_QUESTIONNAIRE_LANGUAGES
from questionnaires.translations import questionnaire_translation_completeness
from reviews.factories import ReviewerTokenFactory, ReviewCycleFactory
from reviews.models import Response


class QuestionnaireTranslationBuilderTests(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory(name='Builder organization')
        self.user = User.objects.create_user(
            username='questionnaire-editor',
            password='test-password',
        )
        UserProfileFactory(user=self.user, organization=self.organization)
        self.client.force_login(self.user)

        self.questionnaire = QuestionnaireFactory(
            organization=self.organization,
            name='Canonical questionnaire',
            description='Canonical questionnaire description',
        )
        self.section = QuestionSectionFactory(
            questionnaire=self.questionnaire,
            title='Canonical section',
            description='Canonical section description',
        )
        self.rating_question = QuestionFactory(
            section=self.section,
            question_type='rating',
            question_text='Canonical rating question',
            config={'min': 1, 'max': 2, 'labels': {'1': 'Poor', '2': 'Good'}},
            order=0,
        )
        self.likert_question = QuestionFactory(
            section=self.section,
            question_type='likert',
            question_text='Canonical Likert question',
            config={'scale': ['Often', 'Always']},
            order=1,
        )
        self.single_choice_question = QuestionFactory(
            section=self.section,
            question_type='single_choice',
            question_text='Canonical single choice question',
            config={
                'choices': ['Often', 'Always'],
                'weights': [1, 2],
                'dreyfus_mapping': {'skill': 1.5},
            },
            order=2,
        )
        self.multiple_choice_question = QuestionFactory(
            section=self.section,
            question_type='multiple_choice',
            question_text='Canonical multiple choice question',
            config={'choices': ['Often', 'Always'], 'scoring_enabled': True},
            order=3,
        )
        self.scale_question = QuestionFactory(
            section=self.section,
            question_type='scale',
            question_text='Canonical scale question',
            config={
                'min': 1,
                'max': 10,
                'step': 1,
                'min_label': 'Not at all',
                'max_label': 'Extremely',
            },
            order=4,
        )
        self.text_question = QuestionFactory(
            section=self.section,
            question_type='text',
            question_text='Canonical text question',
            config={},
            order=5,
        )

    @property
    def edit_url(self):
        return reverse('questionnaire_edit', args=[self.questionnaire.id])

    def add_french(self):
        response = self.client.post(self.edit_url, {
            'action': 'add_translation_language',
            'language_code': 'fr',
        })
        self.assertRedirects(response, f'{self.edit_url}?lang=fr', fetch_redirect_response=False)

    def translation_payload(self):
        return {
            'questionnaire': {
                'name': 'Questionnaire traduit',
                'description': 'Description traduite',
            },
            'sections': [{
                'id': self.section.id,
                'title': 'Section traduite',
                'description': 'Description de section traduite',
            }],
            'questions': [
                {
                    'id': self.rating_question.id,
                    'question_text': 'Question de notation',
                    'translated_config': {
                        'labels': {'1': 'Faible', '2': 'Bien'},
                    },
                },
                {
                    'id': self.likert_question.id,
                    'question_text': 'Question Likert',
                    'translated_config': {'scale': ['Souvent', 'Toujours']},
                },
                {
                    'id': self.single_choice_question.id,
                    'question_text': 'Question à choix unique',
                    'translated_config': {'choices': ['Souvent', 'Toujours']},
                },
                {
                    'id': self.multiple_choice_question.id,
                    'question_text': 'Question à choix multiple',
                    'translated_config': {'choices': ['Souvent', 'Toujours']},
                },
                {
                    'id': self.scale_question.id,
                    'question_text': 'Question à échelle',
                    'translated_config': {
                        'min_label': 'Pas du tout',
                        'max_label': 'Extrêmement',
                    },
                },
                {
                    'id': self.text_question.id,
                    'question_text': 'Question ouverte',
                    'translated_config': {},
                },
            ],
        }

    def save_translation_payload(self, payload, language='fr'):
        return self.client.post(self.edit_url, {
            'action': 'save_all_translations',
            'lang': language,
            'translation_payload': json.dumps(payload),
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_add_supported_language_creates_no_duplicate_questionnaire_structure(self):
        existing_questionnaire_count = Questionnaire.objects.filter(
            organization=self.organization
        ).count()
        self.add_french()

        self.assertEqual(
            Questionnaire.objects.filter(organization=self.organization).count(),
            existing_questionnaire_count,
        )
        self.assertEqual(self.questionnaire.sections.count(), 1)
        self.assertEqual(self.section.questions.count(), 6)
        self.assertEqual(
            list(self.questionnaire.translations.values_list('language_code', flat=True)),
            ['fr'],
        )

    def test_source_duplicate_and_unsupported_languages_are_rejected(self):
        for language_code in ('en-us', 'zz-zz'):
            response = self.client.post(self.edit_url, {
                'action': 'add_translation_language',
                'language_code': language_code,
            })
            self.assertRedirects(response, self.edit_url, fetch_redirect_response=False)

        self.assertEqual(self.questionnaire.translations.count(), 0)
        self.add_french()
        response = self.client.post(self.edit_url, {
            'action': 'add_translation_language',
            'language_code': 'fr',
        })
        self.assertRedirects(
            response,
            f'{self.edit_url}?lang=fr',
            fetch_redirect_response=False,
        )
        self.assertEqual(self.questionnaire.translations.count(), 1)

    @override_settings(LANGUAGES=[('xx', 'Deployment-specific language')])
    def test_builder_renders_authoritative_language_catalog_independent_of_settings(self):
        QuestionnaireTranslation.objects.create(
            questionnaire=self.questionnaire,
            language_code='fr',
        )

        response = self.client.get(self.edit_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'English (Primary)')
        self.assertContains(response, 'Primary / Source')
        self.assertContains(response, 'English <span class="badge badge-info">')

        add_language_options = response.context['available_language_options']
        expected_languages = [
            language
            for language in SUPPORTED_QUESTIONNAIRE_LANGUAGES
            if language['code'] not in {'en-us', 'fr'}
        ]
        self.assertEqual(
            add_language_options,
            [
                {'code': language['code'], 'label': language['name']}
                for language in expected_languages
            ],
        )
        for language in expected_languages:
            self.assertContains(
                response,
                f'<option value="{language["code"]}">{language["name"]}</option>',
                html=True,
            )

        self.assertNotContains(response, '<option value="en-us">English</option>', html=True)
        self.assertNotContains(response, '<option value="fr">French</option>', html=True)
        self.assertNotContains(
            response,
            '<option value="xx">Deployment-specific language</option>',
            html=True,
        )

    def test_remove_translation_deletes_only_current_questionnaire_language(self):
        self.add_french()
        other_questionnaire = QuestionnaireFactory(organization=self.organization)
        other_section = QuestionSectionFactory(questionnaire=other_questionnaire)
        other_question = QuestionFactory(section=other_section)
        QuestionnaireTranslation.objects.create(
            questionnaire=other_questionnaire,
            language_code='fr',
            name='Other language',
        )
        QuestionSectionTranslation.objects.create(
            section=other_section,
            language_code='fr',
            title='Other section',
        )
        QuestionTranslation.objects.create(
            question=other_question,
            language_code='fr',
            question_text='Other question',
        )
        other_organization_questionnaire = QuestionnaireFactory()
        other_organization_section = QuestionSectionFactory(
            questionnaire=other_organization_questionnaire
        )
        other_organization_question = QuestionFactory(
            section=other_organization_section
        )
        QuestionnaireTranslation.objects.create(
            questionnaire=other_organization_questionnaire,
            language_code='fr',
            name='Other organization',
        )
        QuestionSectionTranslation.objects.create(
            section=other_organization_section,
            language_code='fr',
            title='Other organization section',
        )
        QuestionTranslation.objects.create(
            question=other_organization_question,
            language_code='fr',
            question_text='Other organization question',
        )

        response = self.client.post(self.edit_url, {
            'action': 'remove_translation_language',
            'language_code': 'fr',
            'lang': 'fr',
        })

        self.assertRedirects(response, self.edit_url, fetch_redirect_response=False)
        self.assertFalse(self.questionnaire.translations.filter(language_code='fr').exists())
        self.assertEqual(
            QuestionnaireTranslation.objects.get(
                questionnaire=other_questionnaire,
                language_code='fr',
            ).name,
            'Other language',
        )
        self.assertEqual(
            QuestionnaireTranslation.objects.get(
                questionnaire=other_organization_questionnaire,
                language_code='fr',
            ).name,
            'Other organization',
        )
        self.assertEqual(self.questionnaire.name, 'Canonical questionnaire')
        self.assertTrue(self.questionnaire.sections.filter(pk=self.section.pk).exists())
        self.assertTrue(self.section.questions.filter(pk=self.rating_question.pk).exists())

    def test_source_language_cannot_be_removed(self):
        response = self.client.post(self.edit_url, {
            'action': 'remove_translation_language',
            'language_code': self.questionnaire.source_language,
        })

        self.assertRedirects(response, self.edit_url, fetch_redirect_response=False)
        self.assertTrue(
            Questionnaire.objects.filter(pk=self.questionnaire.pk).exists()
        )

    def test_questionnaire_translation_saves_blankable_text_without_source_changes(self):
        self.add_french()
        response = self.client.post(f'{self.edit_url}?lang=fr', {
            'action': 'update_questionnaire_translation',
            'lang': 'fr',
            'translated_name': 'Questionnaire traduit',
            'translated_description': '',
        })

        self.assertRedirects(
            response,
            f'{self.edit_url}?lang=fr',
            fetch_redirect_response=False,
        )
        translation = self.questionnaire.translations.get(language_code='fr')
        self.assertEqual(translation.name, 'Questionnaire traduit')
        self.assertEqual(translation.description, '')
        self.questionnaire.refresh_from_db()
        self.assertEqual(self.questionnaire.name, 'Canonical questionnaire')
        self.assertEqual(
            self.questionnaire.description,
            'Canonical questionnaire description',
        )

    def test_saving_empty_section_and_question_creates_no_empty_translation_rows(self):
        self.add_french()
        self.client.post(f'{self.edit_url}?lang=fr', {
            'action': 'update_section_translation',
            'lang': 'fr',
            'section_id': self.section.id,
            'translated_title': '',
            'translated_description': '',
        })
        self.client.post(f'{self.edit_url}?lang=fr', {
            'action': 'update_question_translation',
            'lang': 'fr',
            'question_id': self.text_question.id,
            'translated_question_text': '',
        })

        self.assertFalse(self.section.translations.filter(language_code='fr').exists())
        self.assertFalse(
            self.text_question.translations.filter(language_code='fr').exists()
        )

    def test_section_translation_is_scoped_and_canonical_fields_are_unchanged(self):
        self.add_french()
        response = self.client.post(f'{self.edit_url}?lang=fr', {
            'action': 'update_section_translation',
            'lang': 'fr',
            'section_id': self.section.id,
            'translated_title': 'Section traduite',
            'translated_description': 'Description traduite',
        })
        self.assertEqual(response.status_code, 302)
        translation = self.section.translations.get(language_code='fr')
        self.assertEqual(translation.title, 'Section traduite')
        self.assertEqual(translation.description, 'Description traduite')
        self.section.refresh_from_db()
        self.assertEqual(self.section.title, 'Canonical section')
        self.assertEqual(self.section.description, 'Canonical section description')

        other_section = QuestionSectionFactory()
        response = self.client.post(f'{self.edit_url}?lang=fr', {
            'action': 'update_section_translation',
            'lang': 'fr',
            'section_id': other_section.id,
            'translated_title': 'Tampered section',
            'translated_description': '',
        })
        self.assertEqual(response.status_code, 404)
        self.assertFalse(other_section.translations.exists())

    def test_question_translations_save_supported_config_without_changing_canonical_config(self):
        self.add_french()
        original_configs = {
            question.pk: deepcopy(question.config)
            for question in (
                self.rating_question,
                self.likert_question,
                self.single_choice_question,
                self.multiple_choice_question,
                self.scale_question,
                self.text_question,
            )
        }
        cases = (
            (self.rating_question, {
                'rating_label_0': 'Faible',
                'rating_label_1': 'Bon',
            }),
            (self.likert_question, {
                'option_label': ['Souvent', 'Toujours'],
            }),
            (self.single_choice_question, {
                'option_label': ['Souvent', 'Toujours'],
                'weights': ['999', '999'],
                'question_type': 'text',
                'required': 'off',
                'order': '99',
                'dreyfus_mapping': '{"agency": 99}',
            }),
            (self.multiple_choice_question, {
                'option_label': ['Souvent', 'Toujours'],
            }),
            (self.scale_question, {
                'translated_min_label': 'Pas du tout',
                'translated_max_label': 'Extrêmement',
            }),
            (self.text_question, {}),
        )
        for question, fields in cases:
            data = {
                'action': 'update_question_translation',
                'lang': 'fr',
                'question_id': question.id,
                'translated_question_text': f'Traduction {question.id}',
            }
            for key, value in fields.items():
                if isinstance(value, list):
                    data[key] = value
                else:
                    data[key] = value
            response = self.client.post(f'{self.edit_url}?lang=fr', data)
            self.assertEqual(response.status_code, 302)

        expected_configs = {
            self.rating_question.id: {'labels': {'1': 'Faible', '2': 'Bon'}},
            self.likert_question.id: {'scale': ['Souvent', 'Toujours']},
            self.single_choice_question.id: {'choices': ['Souvent', 'Toujours']},
            self.multiple_choice_question.id: {'choices': ['Souvent', 'Toujours']},
            self.scale_question.id: {
                'min_label': 'Pas du tout',
                'max_label': 'Extrêmement',
            },
            self.text_question.id: {},
        }
        for question, _fields in cases:
            question.refresh_from_db()
            self.assertEqual(question.config, original_configs[question.pk])
            translation = question.translations.get(language_code='fr')
            self.assertEqual(
                translation.question_text,
                f'Traduction {question.id}',
            )
            self.assertEqual(translation.translated_config, expected_configs[question.id])

        response = self.client.post(f'{self.edit_url}?lang=fr', {
            'action': 'update_question_translation',
            'lang': 'fr',
            'question_id': QuestionFactory(section=QuestionSectionFactory()).id,
            'translated_question_text': 'Tampered',
        })
        self.assertEqual(response.status_code, 404)

    def test_translation_mode_is_separate_from_ui_language_and_hides_structure_actions(self):
        self.add_french()

        translated_response = self.client.get(f'{self.edit_url}?lang=fr')
        self.assertEqual(translated_response.status_code, 200)
        self.assertContains(translated_response, 'Save translations')
        self.assertContains(translated_response, 'id="translation-workspace"')
        self.assertContains(translated_response, 'Canonical questionnaire')
        self.assertContains(translated_response, 'Canonical section')
        self.assertContains(translated_response, 'Canonical rating question')
        self.assertContains(
            translated_response,
            f'data-translation-path="questions.{self.rating_question.id}.question_text"',
        )
        self.assertContains(
            translated_response,
            'to change questionnaire structure.',
        )
        self.assertNotContains(translated_response, 'name="action" value="add_section"')
        self.assertNotContains(translated_response, 'name="action" value="delete_question"')

        source_response = self.client.get(f'{self.edit_url}?lang=en-us')
        self.assertEqual(source_response.status_code, 200)
        self.assertNotContains(source_response, 'Save translations')
        self.assertNotContains(source_response, 'id="translation-workspace"')
        self.assertContains(source_response, 'name="action" value="add_section"')
        self.assertContains(source_response, 'name="action" value="add_question"')

        fallback_response = self.client.get(f'{self.edit_url}?lang=zz-zz')
        self.assertEqual(fallback_response.status_code, 200)
        self.assertContains(fallback_response, 'name="action" value="add_section"')
        self.assertNotContains(fallback_response, 'data-translation-path="questions.')
        self.assertNotContains(fallback_response, 'value="zz-zz"')

    def test_bulk_translation_save_updates_all_displayed_translation_fields(self):
        self.add_french()
        original_configs = {
            question.pk: deepcopy(question.config)
            for question in (
                self.rating_question,
                self.likert_question,
                self.single_choice_question,
                self.multiple_choice_question,
                self.scale_question,
                self.text_question,
            )
        }

        response = self.save_translation_payload(self.translation_payload())

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result['success'])
        self.assertEqual(result['language'], 'fr')
        self.assertEqual(result['completeness']['percentage'], 100)
        questionnaire_translation = self.questionnaire.translations.get(
            language_code='fr'
        )
        self.assertEqual(questionnaire_translation.name, 'Questionnaire traduit')
        self.assertEqual(
            questionnaire_translation.description,
            'Description traduite',
        )
        self.assertEqual(
            self.section.translations.get(language_code='fr').title,
            'Section traduite',
        )
        expected_configs = {
            self.rating_question.id: {'labels': {'1': 'Faible', '2': 'Bien'}},
            self.likert_question.id: {'scale': ['Souvent', 'Toujours']},
            self.single_choice_question.id: {'choices': ['Souvent', 'Toujours']},
            self.multiple_choice_question.id: {'choices': ['Souvent', 'Toujours']},
            self.scale_question.id: {
                'min_label': 'Pas du tout',
                'max_label': 'Extrêmement',
            },
            self.text_question.id: {},
        }
        for question_id, expected_config in expected_configs.items():
            question = Question.objects.get(pk=question_id)
            translation = question.translations.get(language_code='fr')
            self.assertTrue(translation.question_text)
            self.assertEqual(translation.translated_config, expected_config)
            self.assertEqual(question.config, original_configs[question_id])

    def test_rendered_bulk_save_url_resolves_and_accepts_valid_post(self):
        self.add_french()
        page = self.client.get(f'{self.edit_url}?lang=fr')
        self.assertEqual(page.status_code, 200)
        expected_url = f'{self.edit_url}?lang=fr'
        self.assertContains(
            page,
            f'id="translation-workspace" method="post" action="{expected_url}"',
        )
        self.assertContains(page, 'name="action" value="save_all_translations"')
        self.assertContains(page, "fetch(form.getAttribute('action')")
        self.assertNotContains(page, 'fetch(form.action,')
        self.assertEqual(resolve(self.edit_url).url_name, 'questionnaire_edit')

        response = self.client.post(
            expected_url,
            {
                'action': 'save_all_translations',
                'lang': 'fr',
                'translation_payload': json.dumps(self.translation_payload()),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertNotEqual(response.status_code, 404)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    def test_bulk_translation_save_rejects_invalid_payload_without_partial_writes(self):
        self.add_french()
        payload = self.translation_payload()
        payload['questions'][1]['translated_config']['scale'] = ['Incomplet']

        response = self.save_translation_payload(payload)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertFalse(
            self.section.translations.filter(language_code='fr').exists()
        )
        self.assertFalse(
            self.rating_question.translations.filter(language_code='fr').exists()
        )
        self.assertEqual(
            self.questionnaire.translations.get(language_code='fr').name,
            '',
        )

    def test_bulk_translation_save_rejects_source_or_unavailable_language(self):
        self.add_french()
        payload = self.translation_payload()

        for language in ('en-us', 'de'):
            response = self.save_translation_payload(payload, language=language)
            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.json()['success'])

    def test_bulk_translation_save_rejects_malformed_or_out_of_scope_ids(self):
        self.add_french()
        other_section = QuestionSectionFactory()
        other_question = QuestionFactory(section=other_section)
        payloads = []

        duplicate_section = self.translation_payload()
        duplicate_section['sections'].append(deepcopy(duplicate_section['sections'][0]))
        payloads.append(duplicate_section)

        foreign_section = self.translation_payload()
        foreign_section['sections'][0]['id'] = other_section.id
        payloads.append(foreign_section)

        duplicate_question = self.translation_payload()
        duplicate_question['questions'].append(
            deepcopy(duplicate_question['questions'][0])
        )
        payloads.append(duplicate_question)

        foreign_question = self.translation_payload()
        foreign_question['questions'][0]['id'] = other_question.id
        payloads.append(foreign_question)

        for payload in payloads:
            response = self.save_translation_payload(payload)
            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.json()['success'])
            self.assertFalse(
                self.section.translations.filter(language_code='fr').exists()
            )

        malformed_response = self.client.post(self.edit_url, {
            'action': 'save_all_translations',
            'lang': 'fr',
            'translation_payload': '{',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(malformed_response.status_code, 400)
        self.assertFalse(malformed_response.json()['success'])

    def test_bulk_translation_save_creates_rows_lazily_for_blank_content(self):
        self.add_french()
        payload = self.translation_payload()
        payload['questionnaire'] = {'name': '', 'description': ''}
        payload['sections'] = [{
            'id': self.section.id,
            'title': '',
            'description': '',
        }]
        payload['questions'] = [
            {
                'id': question.id,
                'question_text': '',
                'translated_config': (
                    {'labels': {'1': '', '2': ''}}
                    if question == self.rating_question else
                    {'scale': ['', '']}
                    if question == self.likert_question else
                    {'choices': ['', '']}
                    if question in (
                        self.single_choice_question,
                        self.multiple_choice_question,
                    ) else
                    {'min_label': '', 'max_label': ''}
                    if question == self.scale_question else
                    {}
                ),
            }
            for question in (
                self.rating_question,
                self.likert_question,
                self.single_choice_question,
                self.multiple_choice_question,
                self.scale_question,
                self.text_question,
            )
        ]

        response = self.save_translation_payload(payload)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.section.translations.filter(language_code='fr').exists())
        for question in (
            self.rating_question,
            self.likert_question,
            self.single_choice_question,
            self.multiple_choice_question,
            self.scale_question,
            self.text_question,
        ):
            self.assertFalse(question.translations.filter(language_code='fr').exists())

    def test_anonymous_user_cannot_edit_translations(self):
        self.client.logout()
        response = self.client.post(self.edit_url, {
            'action': 'add_translation_language',
            'language_code': 'fr',
        })

        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.questionnaire.translations.exists())

    def test_structural_post_in_translation_mode_is_rejected(self):
        self.add_french()
        original_section_count = self.questionnaire.sections.count()

        response = self.client.post(f'{self.edit_url}?lang=fr', {
            'action': 'add_section',
            'lang': 'fr',
            'section_title': 'Must not exist',
        })

        self.assertRedirects(
            response,
            f'{self.edit_url}?lang=fr',
            fetch_redirect_response=False,
        )
        self.assertEqual(self.questionnaire.sections.count(), original_section_count)

    def test_translation_save_does_not_change_response_value(self):
        self.add_french()
        cycle = ReviewCycleFactory(questionnaire=self.questionnaire)
        token = ReviewerTokenFactory(cycle=cycle, category='peer')
        response = Response.objects.create(
            cycle=cycle,
            question=self.single_choice_question,
            token=token,
            category='peer',
            answer_data={'value': 'Often'},
        )
        self.client.post(f'{self.edit_url}?lang=fr', {
            'action': 'update_question_translation',
            'lang': 'fr',
            'question_id': self.single_choice_question.id,
            'translated_question_text': 'Fréquence?',
            'option_label': ['Souvent', 'Toujours'],
        })

        response.refresh_from_db()
        self.assertEqual(response.answer_data, {'value': 'Often'})

    def test_other_organization_cannot_access_or_edit_questionnaire_translation(self):
        other_organization = OrganizationFactory(name='Other organization')
        other_user = User.objects.create_user(
            username='other-editor',
            password='test-password',
        )
        UserProfileFactory(user=other_user, organization=other_organization)
        self.client.force_login(other_user)

        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 404)
        response = self.client.post(self.edit_url, {
            'action': 'update_questionnaire_translation',
            'lang': 'fr',
            'translated_name': 'Tampered',
        })
        self.assertEqual(response.status_code, 404)


class QuestionnaireTranslationCompletenessTests(TestCase):
    def setUp(self):
        self.questionnaire = QuestionnaireFactory(
            name='Canonical questionnaire',
            description='',
        )
        self.section = QuestionSectionFactory(
            questionnaire=self.questionnaire,
            title='Canonical section',
            description='',
        )
        self.questions = [
            QuestionFactory(
                section=self.section,
                question_type='single_choice',
                question_text='Single choice question',
                config={'choices': ['Often', 'Always']},
                order=0,
            ),
            QuestionFactory(
                section=self.section,
                question_type='likert',
                question_text='Likert question',
                config={'scale': ['Agree', 'Disagree']},
                order=1,
            ),
            QuestionFactory(
                section=self.section,
                question_type='rating',
                question_text='Rating question',
                config={'labels': {'1': 'Poor', '5': 'Excellent'}},
                order=2,
            ),
            QuestionFactory(
                section=self.section,
                question_type='scale',
                question_text='Scale question',
                config={'min_label': 'Not at all', 'max_label': ''},
                order=3,
            ),
            QuestionFactory(
                section=self.section,
                question_type='text',
                question_text='Text question',
                config={},
                order=4,
            ),
            QuestionFactory(
                section=self.section,
                question_type='text',
                question_text='',
                config={},
                order=5,
            ),
        ]

    def test_partial_completeness_counts_fields_and_excludes_blank_canonical_optional_content(self):
        QuestionnaireTranslation.objects.create(
            questionnaire=self.questionnaire,
            language_code='fr',
            name='Questionnaire traduit',
        )
        QuestionSectionTranslation.objects.create(
            section=self.section,
            language_code='fr',
            title='Section traduite',
        )
        QuestionTranslation.objects.create(
            question=self.questions[0],
            language_code='fr',
            question_text='Question à choix',
            translated_config={'choices': ['Souvent', '']},
        )
        QuestionTranslation.objects.create(
            question=self.questions[1],
            language_code='fr',
            translated_config={'scale': ['D’accord', '']},
        )

        result = questionnaire_translation_completeness(self.questionnaire, 'fr')

        self.assertEqual(result, {
            'translated_count': 5,
            'total_count': 14,
            'percentage': 36,
            'complete': False,
        })

    def test_complete_translation_has_complete_state_and_removal_has_no_cached_state(self):
        QuestionnaireTranslation.objects.create(
            questionnaire=self.questionnaire,
            language_code='fr',
            name='Questionnaire traduit',
        )
        QuestionSectionTranslation.objects.create(
            section=self.section,
            language_code='fr',
            title='Section traduite',
        )
        config_values = (
            {'choices': ['Souvent', 'Toujours']},
            {'scale': ['D’accord', 'Pas d’accord']},
            {'labels': {'1': 'Faible', '5': 'Excellent'}},
            {'min_label': 'Pas du tout'},
            {},
            {},
        )
        for question, translated_config in zip(self.questions, config_values):
            QuestionTranslation.objects.create(
                question=question,
                language_code='fr',
                question_text=question.question_text or '',
                translated_config=translated_config,
            )

        result = questionnaire_translation_completeness(self.questionnaire, 'fr')
        self.assertEqual(result, {
            'translated_count': 14,
            'total_count': 14,
            'percentage': 100,
            'complete': True,
        })

        self.questionnaire.translations.filter(language_code='fr').delete()
        self.section.translations.filter(language_code='fr').delete()
        QuestionTranslation.objects.filter(
            question__section__questionnaire=self.questionnaire,
            language_code='fr',
        ).delete()
        self.assertEqual(
            questionnaire_translation_completeness(self.questionnaire, 'fr'),
            {
                'translated_count': 0,
                'total_count': 14,
                'percentage': 0,
                'complete': False,
            },
        )
