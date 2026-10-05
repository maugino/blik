from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from questionnaires.factories import (
    LikertQuestionFactory,
    QuestionnaireFactory,
    QuestionSectionFactory,
    RatingQuestionFactory,
    QuestionFactory,
)
from questionnaires.models import (
    QuestionnaireTranslation,
    QuestionSectionTranslation,
    QuestionTranslation,
)


class QuestionnaireTranslationModelTests(TestCase):
    def setUp(self):
        self.questionnaire = QuestionnaireFactory(
            name='Team Feedback',
            description='Canonical description',
        )
        self.section = QuestionSectionFactory(
            questionnaire=self.questionnaire,
            title='Communication',
            description='Canonical section description',
        )
        self.question = QuestionFactory(
            section=self.section,
            question_type='single_choice',
            question_text='How often do you collaborate?',
            config={
                'choices': ['Often', 'Always'],
                'weights': [2, 3],
                'scoring_enabled': True,
                'chart_weight': 1.5,
            },
        )

    def test_existing_style_questionnaire_uses_safe_source_language_default(self):
        questionnaire = QuestionnaireFactory()
        self.assertEqual(questionnaire.source_language, 'en-us')

    def test_source_language_and_translation_language_are_normalized(self):
        questionnaire = QuestionnaireFactory(source_language='FR_fr')
        translation = QuestionnaireTranslation.objects.create(
            questionnaire=questionnaire,
            language_code='ES_mx',
            name='Retroalimentación',
        )

        self.assertEqual(questionnaire.source_language, 'fr-fr')
        self.assertEqual(translation.language_code, 'es-mx')

    def test_invalid_language_codes_are_rejected(self):
        questionnaire = QuestionnaireFactory()
        with self.assertRaises(ValidationError):
            QuestionnaireTranslation.objects.create(
                questionnaire=questionnaire,
                language_code='',
                name='Nom',
            )
        with self.assertRaises(ValidationError):
            QuestionnaireFactory(source_language='not a language')

    def test_duplicate_translations_are_rejected_for_each_model(self):
        QuestionnaireTranslation.objects.create(
            questionnaire=self.questionnaire,
            language_code='fr',
            name='Retour',
        )
        with self.assertRaises(ValidationError):
            QuestionnaireTranslation.objects.create(
                questionnaire=self.questionnaire,
                language_code='FR',
                name='Autre',
            )

        QuestionSectionTranslation.objects.create(
            section=self.section,
            language_code='fr',
            title='Communication',
        )
        with self.assertRaises(ValidationError):
            QuestionSectionTranslation.objects.create(
                section=self.section,
                language_code='fr',
                title='Autre',
            )

        QuestionTranslation.objects.create(
            question=self.question,
            language_code='fr',
            question_text='À quelle fréquence collaborez-vous?',
        )
        with self.assertRaises(ValidationError):
            QuestionTranslation.objects.create(
                question=self.question,
                language_code='fr',
                question_text='Autre',
            )

    def test_database_constraints_enforce_one_translation_per_language(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                QuestionnaireTranslation.objects.bulk_create([
                    QuestionnaireTranslation(
                        questionnaire=self.questionnaire,
                        language_code='fr',
                        name='Premier',
                    ),
                    QuestionnaireTranslation(
                        questionnaire=self.questionnaire,
                        language_code='fr',
                        name='Deuxième',
                    ),
                ])

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                QuestionSectionTranslation.objects.bulk_create([
                    QuestionSectionTranslation(
                        section=self.section,
                        language_code='fr',
                        title='Premier',
                    ),
                    QuestionSectionTranslation(
                        section=self.section,
                        language_code='fr',
                        title='Deuxième',
                    ),
                ])

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                QuestionTranslation.objects.bulk_create([
                    QuestionTranslation(
                        question=self.question,
                        language_code='fr',
                        question_text='Premier',
                    ),
                    QuestionTranslation(
                        question=self.question,
                        language_code='fr',
                        question_text='Deuxième',
                    ),
                ])

    def test_source_language_translation_rows_are_rejected(self):
        with self.assertRaises(ValidationError):
            QuestionnaireTranslation.objects.create(
                questionnaire=self.questionnaire,
                language_code='EN_us',
                name='Duplicate source',
            )
        with self.assertRaises(ValidationError):
            QuestionSectionTranslation.objects.create(
                section=self.section,
                language_code='en-US',
                title='Duplicate source',
            )
        with self.assertRaises(ValidationError):
            QuestionTranslation.objects.create(
                question=self.question,
                language_code='en-us',
                question_text='Duplicate source',
            )

    def test_translation_deletion_cascades_with_parent_objects(self):
        QuestionnaireTranslation.objects.create(
            questionnaire=self.questionnaire,
            language_code='fr',
            name='Équipe',
        )
        QuestionSectionTranslation.objects.create(
            section=self.section,
            language_code='fr',
            title='Communication',
        )
        QuestionTranslation.objects.create(
            question=self.question,
            language_code='fr',
            question_text='Question traduite',
        )

        self.questionnaire.delete()

        self.assertEqual(QuestionnaireTranslation.objects.count(), 0)
        self.assertEqual(QuestionSectionTranslation.objects.count(), 0)
        self.assertEqual(QuestionTranslation.objects.count(), 0)

    def test_text_resolution_uses_translation_or_canonical_fallback(self):
        QuestionnaireTranslation.objects.create(
            questionnaire=self.questionnaire,
            language_code='fr',
            name='Commentaires d’équipe',
            description='Description traduite',
        )
        QuestionSectionTranslation.objects.create(
            section=self.section,
            language_code='fr',
            title='Communication traduite',
            description='Description de section traduite',
        )
        QuestionTranslation.objects.create(
            question=self.question,
            language_code='fr',
            question_text='À quelle fréquence collaborez-vous?',
        )
        QuestionnaireTranslation.objects.create(
            questionnaire=self.questionnaire,
            language_code='es',
            name='Comentarios de equipo',
        )

        self.assertEqual(self.questionnaire.resolve_name('fr'), 'Commentaires d’équipe')
        self.assertEqual(
            self.questionnaire.resolve_description('fr'),
            'Description traduite',
        )
        self.assertEqual(self.section.resolve_title('fr'), 'Communication traduite')
        self.assertEqual(
            self.section.resolve_description('fr'),
            'Description de section traduite',
        )
        self.assertEqual(
            self.question.resolve_question_text('fr'),
            'À quelle fréquence collaborez-vous?',
        )
        self.assertEqual(self.questionnaire.resolve_description('en-us'), 'Canonical description')
        self.assertEqual(self.section.resolve_title('en-us'), 'Communication')
        self.assertEqual(
            self.section.resolve_description('en-us'),
            'Canonical section description',
        )
        self.assertEqual(
            self.question.resolve_question_text('en-us'),
            'How often do you collaborate?',
        )
        self.assertEqual(self.question.resolve_config('en-us'), self.question.config)
        self.assertEqual(
            self.question.get_display_options('invalid language'),
            [
                {'value': 'Often', 'label': 'Often'},
                {'value': 'Always', 'label': 'Always'},
            ],
        )
        self.assertEqual(self.questionnaire.resolve_name('de'), 'Team Feedback')
        self.assertEqual(self.questionnaire.resolve_name('es-MX'), 'Team Feedback')
        self.assertEqual(self.questionnaire.resolve_name('en-us'), 'Team Feedback')
        self.assertEqual(self.questionnaire.resolve_name('invalid language'), 'Team Feedback')

    def test_blank_translated_fields_fall_back_to_canonical_content(self):
        QuestionnaireTranslation.objects.create(
            questionnaire=self.questionnaire,
            language_code='fr',
            name='',
            description='',
        )
        QuestionSectionTranslation.objects.create(
            section=self.section,
            language_code='fr',
            title='',
            description='',
        )
        QuestionTranslation.objects.create(
            question=self.question,
            language_code='fr',
            question_text='',
        )

        self.assertEqual(self.questionnaire.resolve_name('fr'), 'Team Feedback')
        self.assertEqual(
            self.questionnaire.resolve_description('fr'),
            'Canonical description',
        )
        self.assertEqual(self.section.resolve_title('fr'), 'Communication')
        self.assertEqual(
            self.section.resolve_description('fr'),
            'Canonical section description',
        )
        self.assertEqual(
            self.question.resolve_question_text('fr'),
            'How often do you collaborate?',
        )

    def test_choice_translation_separates_canonical_values_and_display_labels(self):
        QuestionTranslation.objects.create(
            question=self.question,
            language_code='fr',
            question_text='À quelle fréquence collaborez-vous?',
            translated_config={'choices': ['Souvent', 'Toujours']},
        )

        options = self.question.get_display_options('fr')

        self.assertEqual(options, [
            {'value': 'Often', 'label': 'Souvent'},
            {'value': 'Always', 'label': 'Toujours'},
        ])
        resolved_config = self.question.resolve_config('fr')
        self.assertEqual(resolved_config['choices'], ['Souvent', 'Toujours'])
        self.assertEqual(resolved_config['weights'], [2, 3])
        self.assertTrue(resolved_config['scoring_enabled'])
        self.assertEqual(resolved_config['chart_weight'], 1.5)
        self.assertEqual(self.question.config['choices'], ['Often', 'Always'])

    def test_incomplete_choice_labels_fall_back_by_position(self):
        QuestionTranslation.objects.create(
            question=self.question,
            language_code='fr',
            translated_config={'choices': ['Souvent', '']},
        )

        self.assertEqual(self.question.get_display_options('fr'), [
            {'value': 'Often', 'label': 'Souvent'},
            {'value': 'Always', 'label': 'Always'},
        ])

    def test_likert_translation_keeps_canonical_submitted_values(self):
        question = LikertQuestionFactory(
            section=self.section,
            config={'scale': ['Often', 'Always'], 'scoring_enabled': True},
        )
        QuestionTranslation.objects.create(
            question=question,
            language_code='fr',
            translated_config={'scale': ['Souvent', 'Toujours']},
        )

        self.assertEqual(question.get_display_options('fr'), [
            {'value': 'Often', 'label': 'Souvent'},
            {'value': 'Always', 'label': 'Toujours'},
        ])
        self.assertEqual(question.config['scale'], ['Often', 'Always'])

    def test_multiple_choice_translation_keeps_canonical_submitted_values(self):
        question = QuestionFactory(
            section=self.section,
            question_type='multiple_choice',
            config={'choices': ['Often', 'Always']},
        )
        QuestionTranslation.objects.create(
            question=question,
            language_code='fr',
            translated_config={'choices': ['Souvent', 'Toujours']},
        )

        self.assertEqual(question.get_display_options('fr'), [
            {'value': 'Often', 'label': 'Souvent'},
            {'value': 'Always', 'label': 'Toujours'},
        ])

    def test_rating_labels_map_to_canonical_values(self):
        question = RatingQuestionFactory(
            section=self.section,
            config={
                'min': 1,
                'max': 3,
                'labels': {'1': 'Poor', '3': 'Excellent'},
            },
        )
        QuestionTranslation.objects.create(
            question=question,
            language_code='fr',
            translated_config={'labels': {'1': 'Faible'}},
        )

        self.assertEqual(question.get_display_options('fr'), [
            {'value': 1, 'label': 'Faible'},
            {'value': 2, 'label': '2'},
            {'value': 3, 'label': 'Excellent'},
        ])

    def test_scale_translation_changes_only_endpoint_labels(self):
        question = QuestionFactory(
            section=self.section,
            question_type='scale',
            config={'min': 1, 'max': 10, 'step': 2, 'min_label': 'Not at all'},
        )
        QuestionTranslation.objects.create(
            question=question,
            language_code='fr',
            translated_config={
                'min_label': 'Pas du tout',
                'max_label': 'Extrêmement',
            },
        )

        self.assertEqual(question.resolve_config('fr'), {
            'min': 1,
            'max': 10,
            'step': 2,
            'min_label': 'Pas du tout',
            'max_label': 'Extrêmement',
        })

    def test_unsafe_translated_configuration_is_rejected(self):
        likert_question = LikertQuestionFactory(
            section=self.section,
            config={'scale': ['Often', 'Always']},
        )
        with self.assertRaises(ValidationError):
            QuestionTranslation.objects.create(
                question=likert_question,
                language_code='fr',
                translated_config={'scale': ['Souvent']},
            )

        with self.assertRaises(ValidationError):
            QuestionTranslation.objects.create(
                question=self.question,
                language_code='fr',
                translated_config={'choices': ['Souvent'], 'weights': [1]},
            )

        rating_question = RatingQuestionFactory(
            section=self.section,
            config={'labels': {'1': 'Poor', '5': 'Excellent'}},
        )
        with self.assertRaises(ValidationError):
            QuestionTranslation.objects.create(
                question=rating_question,
                language_code='fr',
                translated_config={'labels': {'2': 'Moyen'}},
            )

        scale_question = QuestionFactory(
            section=self.section,
            question_type='scale',
            config={'min': 1, 'max': 5, 'step': 1},
        )
        with self.assertRaises(ValidationError):
            QuestionTranslation.objects.create(
                question=scale_question,
                language_code='fr',
                translated_config={'min': 'Un', 'step': 1},
            )

    def test_translation_saving_does_not_change_question_configuration(self):
        original_config = self.question.config.copy()
        QuestionTranslation.objects.create(
            question=self.question,
            language_code='fr',
            translated_config={'choices': ['Souvent', 'Toujours']},
        )
        self.question.refresh_from_db()

        self.assertEqual(self.question.config, original_config)
