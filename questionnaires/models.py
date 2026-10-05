import uuid
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import models
from core.models import TimeStampedModel, Organization
from core.managers import QuestionnaireManager
from core.languages import normalize_language_code


def _translation_for_language(translations, language_code, source_language):
    normalized_language = normalize_language_code(language_code)
    if not normalized_language or normalized_language == source_language:
        return None
    prefetched_translations = getattr(
        translations.instance,
        '_prefetched_objects_cache',
        {},
    ).get('translations')
    if prefetched_translations is not None:
        return next(
            (
                translation for translation in prefetched_translations
                if translation.language_code == normalized_language
            ),
            None,
        )
    return translations.filter(language_code=normalized_language).first()


def _translated_text(translations, language_code, source_language, field_name, source_value):
    translation = _translation_for_language(translations, language_code, source_language)
    if translation is None:
        return source_value
    translated_value = getattr(translation, field_name)
    return translated_value if translated_value and translated_value.strip() else source_value


class Questionnaire(TimeStampedModel):
    """Feedback questionnaire"""
    # Public UUID for external references (API, URLs)
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Public identifier for API and URL usage (non-enumerable)"
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='questionnaires',
        null=True,  # Allow null for existing records and default questionnaires
        blank=True
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    source_language = models.CharField(max_length=35, default='en-us')
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = QuestionnaireManager()

    class Meta:
        db_table = 'questionnaires'
        ordering = ['-is_default', 'name']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        normalized_language = normalize_language_code(self.source_language)
        if not normalized_language:
            raise ValidationError({'source_language': 'Enter a valid language code.'})
        self.source_language = normalized_language

    def save(self, *args, **kwargs):
        normalized_language = normalize_language_code(self.source_language)
        if not normalized_language:
            raise ValidationError({'source_language': 'Enter a valid language code.'})
        self.source_language = normalized_language
        super().save(*args, **kwargs)

    def resolve_name(self, language_code):
        return _translated_text(
            self.translations, language_code, self.source_language, 'name', self.name
        )

    def resolve_description(self, language_code):
        return _translated_text(
            self.translations,
            language_code,
            self.source_language,
            'description',
            self.description,
        )

    @property
    def dreyfus_dimensions(self):
        """Return (has_skill, has_agency) based on question dreyfus_mapping configs.

        A dimension counts as present if any question carries a non-zero weight
        for that dimension in its config['dreyfus_mapping']. Uses the prefetched
        sections/questions relation when available so it doesn't N+1 in list views.
        """
        has_skill = False
        has_agency = False

        for section in self.sections.all():
            for question in section.questions.all():
                mapping = (question.config or {}).get('dreyfus_mapping') or {}
                if not isinstance(mapping, dict):
                    continue
                try:
                    if mapping.get('skill') and float(mapping['skill']) != 0:
                        has_skill = True
                    if mapping.get('agency') and float(mapping['agency']) != 0:
                        has_agency = True
                except (TypeError, ValueError):
                    continue
                if has_skill and has_agency:
                    return has_skill, has_agency

        return has_skill, has_agency

    @property
    def report_type_label(self):
        """Human-readable description of what report this questionnaire produces."""
        has_skill, has_agency = self.dreyfus_dimensions
        if has_skill and has_agency:
            return "Dreyfus (Skill + Agency)"
        if has_skill:
            return "Dreyfus (Skill)"
        if has_agency:
            return "Dreyfus (Agency)"
        return "Standard 360"


class QuestionSection(TimeStampedModel):
    """Section grouping questions within a questionnaire"""
    questionnaire = models.ForeignKey(
        Questionnaire,
        on_delete=models.CASCADE,
        related_name='sections'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        db_table = 'question_sections'
        ordering = ['questionnaire', 'order']
        unique_together = ['questionnaire', 'order']

    def __str__(self):
        return f"{self.questionnaire.name} - {self.title}"

    def resolve_title(self, language_code):
        return _translated_text(
            self.translations,
            language_code,
            self.questionnaire.source_language,
            'title',
            self.title,
        )

    def resolve_description(self, language_code):
        return _translated_text(
            self.translations,
            language_code,
            self.questionnaire.source_language,
            'description',
            self.description,
        )


class Question(TimeStampedModel):
    """Individual question within a section"""

    QUESTION_TYPES = [
        ('rating', 'Rating Scale'),
        ('likert', 'Likert Scale'),
        ('text', 'Free Text'),
        ('single_choice', 'Single Choice'),
        ('multiple_choice', 'Multiple Choice'),
        ('scale', 'Numeric Scale'),
    ]

    # Public UUID for external references (API, URLs)
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Public identifier for API and URL usage (non-enumerable)"
    )

    section = models.ForeignKey(
        QuestionSection,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)

    # JSON field for question configuration
    # For rating: {"min": 1, "max": 5, "labels": {"1": "Poor", "5": "Excellent"}}
    # For likert: {"scale": ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"]}
    # For single_choice:
    #   Basic: {"choices": ["Option 1", "Option 2"]}
    #   With scoring: {"choices": ["Option 1", "Option 2"], "weights": [5, 3], "scoring_enabled": true}
    # For multiple_choice:
    #   Basic: {"choices": ["Option 1", "Option 2"]}
    #   With scoring: {"choices": ["Option 1", "Option 2"], "weights": [5, 3], "scoring_enabled": true}
    #   Note: For multiple_choice, score = sum of selected option weights (rewards selecting more positive attributes)
    # For scale: {"min": 1, "max": 100, "step": 1, "min_label": "Not at all", "max_label": "Extremely"}
    # Optional chart configuration:
    #   "chart_weight": 1.0 (default) - Weight in section average (0.5 = half weight, 2.0 = double weight)
    #   "exclude_from_charts": false (default) - Set true to exclude from chart aggregations
    # Optional Dreyfus model configuration:
    #   "dreyfus_mapping": {"skill": 1.5, "agency": 0.5} - Weights for skill/agency dimensions
    config = models.JSONField(default=dict)

    # Personalized action items for development plans
    # Format: [
    #   {
    #     "text": "Practice pair programming with senior developers",
    #     "threshold": 3.0,  // Include if question score < threshold
    #     "stages": [1, 2, 3]  // Optional: Relevant Dreyfus stages (1-5)
    #   }
    # ]
    action_items = models.JSONField(default=list, blank=True)

    required = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    class Meta:
        db_table = 'questions'
        ordering = ['section', 'order']
        unique_together = ['section', 'order']

    def __str__(self):
        return f"{self.section.title} - {self.question_text[:50]}"

    @property
    def source_language(self):
        return self.section.questionnaire.source_language

    def _translation_for_language(self, language_code):
        return _translation_for_language(
            self.translations, language_code, self.source_language
        )

    def resolve_question_text(self, language_code):
        translation = self._translation_for_language(language_code)
        if translation is None:
            return self.question_text
        translated_text = translation.question_text
        return (
            translated_text
            if translated_text and translated_text.strip()
            else self.question_text
        )

    def resolve_config(self, language_code):
        """Return canonical behavior/config with translated presentation text overlaid."""
        resolved_config = deepcopy(self.config or {})
        translation = self._translation_for_language(language_code)
        if translation is None:
            return resolved_config

        translated_config = translation.translated_config or {}
        if self.question_type == 'rating':
            source_labels = resolved_config.get('labels', {})
            translated_labels = translated_config.get('labels', {})
            if isinstance(source_labels, dict):
                resolved_config['labels'] = {
                    key: translated_labels.get(key) or value
                    for key, value in source_labels.items()
                }
        elif self.question_type in {'likert', 'single_choice', 'multiple_choice'}:
            source_key = 'scale' if self.question_type == 'likert' else 'choices'
            source_values = resolved_config.get(source_key, [])
            translated_values = translated_config.get(source_key, [])
            if isinstance(source_values, list):
                resolved_config[source_key] = [
                    translated_values[index]
                    if (
                        index < len(translated_values)
                        and translated_values[index]
                        and translated_values[index].strip()
                    )
                    else value
                    for index, value in enumerate(source_values)
                ]
        elif self.question_type == 'scale':
            for key in ('min_label', 'max_label'):
                translated_value = translated_config.get(key)
                if translated_value and translated_value.strip():
                    resolved_config[key] = translated_value

        return resolved_config

    def get_display_options(self, language_code):
        """Pair translated labels with canonical values submitted in responses."""
        canonical_config = self.config or {}
        resolved_config = self.resolve_config(language_code)

        if self.question_type == 'rating':
            try:
                minimum = int(canonical_config.get('min', 1))
                maximum = int(canonical_config.get('max', 5))
            except (TypeError, ValueError):
                minimum, maximum = 1, 5
            if maximum < minimum:
                return []
            resolved_labels = resolved_config.get('labels', {})
            return [
                {
                    'value': value,
                    'label': resolved_labels.get(str(value), str(value))
                    if isinstance(resolved_labels, dict)
                    else str(value),
                }
                for value in range(minimum, maximum + 1)
            ]

        if self.question_type == 'likert':
            canonical_values = canonical_config.get('scale', [])
            display_values = resolved_config.get('scale', [])
        elif self.question_type in {'single_choice', 'multiple_choice'}:
            canonical_values = canonical_config.get('choices', [])
            display_values = resolved_config.get('choices', [])
        else:
            return []

        if not isinstance(canonical_values, list) or not isinstance(display_values, list):
            return []
        return [
            {
                'value': value,
                'label': display_values[index]
                if index < len(display_values) and display_values[index]
                else value,
            }
            for index, value in enumerate(canonical_values)
        ]


class QuestionnaireTranslation(TimeStampedModel):
    """Questionnaire text for a non-source language; source rows are redundant."""

    questionnaire = models.ForeignKey(
        Questionnaire,
        on_delete=models.CASCADE,
        related_name='translations',
    )
    language_code = models.CharField(max_length=35)
    name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['questionnaire', 'language_code'],
                name='uniq_questionnaire_translation_language',
            ),
        ]

    def clean(self):
        super().clean()
        normalized_language = normalize_language_code(self.language_code)
        if not normalized_language:
            raise ValidationError({'language_code': 'Enter a valid language code.'})
        self.language_code = normalized_language
        source_language = Questionnaire.objects.filter(
            pk=self.questionnaire_id
        ).values_list('source_language', flat=True).first()
        if source_language and normalized_language == normalize_language_code(source_language):
            raise ValidationError({
                'language_code': 'A translation cannot use the questionnaire source language.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.questionnaire} ({self.language_code})"


class QuestionSectionTranslation(TimeStampedModel):
    section = models.ForeignKey(
        QuestionSection,
        on_delete=models.CASCADE,
        related_name='translations',
    )
    language_code = models.CharField(max_length=35)
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['section', 'language_code'],
                name='uniq_section_translation_language',
            ),
        ]

    def clean(self):
        super().clean()
        normalized_language = normalize_language_code(self.language_code)
        if not normalized_language:
            raise ValidationError({'language_code': 'Enter a valid language code.'})
        self.language_code = normalized_language
        source_language = QuestionSection.objects.filter(
            pk=self.section_id
        ).values_list('questionnaire__source_language', flat=True).first()
        if source_language and normalized_language == normalize_language_code(source_language):
            raise ValidationError({
                'language_code': 'A translation cannot use the questionnaire source language.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.section} ({self.language_code})"


class QuestionTranslation(TimeStampedModel):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='translations',
    )
    language_code = models.CharField(max_length=35)
    question_text = models.TextField(blank=True)
    translated_config = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['question', 'language_code'],
                name='uniq_question_translation_language',
            ),
        ]

    def clean(self):
        super().clean()
        normalized_language = normalize_language_code(self.language_code)
        if not normalized_language:
            raise ValidationError({'language_code': 'Enter a valid language code.'})
        self.language_code = normalized_language
        if (
            self.question_id
            and normalized_language
            == normalize_language_code(self.question.source_language)
        ):
            raise ValidationError({
                'language_code': 'A translation cannot use the questionnaire source language.'
            })

        if not isinstance(self.translated_config, dict):
            raise ValidationError({
                'translated_config': 'Translated configuration must be an object.'
            })
        if any(not isinstance(key, str) for key in self.translated_config):
            raise ValidationError({
                'translated_config': 'Translated configuration keys must be strings.'
            })

        question = Question.objects.select_related(
            'section__questionnaire'
        ).filter(pk=self.question_id).first()
        if question is None:
            return

        if normalized_language == normalize_language_code(question.source_language):
            raise ValidationError({
                'language_code': 'A translation cannot use the questionnaire source language.'
            })

        allowed_keys = {
            'rating': {'labels'},
            'likert': {'scale'},
            'single_choice': {'choices'},
            'multiple_choice': {'choices'},
            'scale': {'min_label', 'max_label'},
            'text': set(),
        }.get(question.question_type, set())
        unsupported_keys = set(self.translated_config) - allowed_keys
        if unsupported_keys:
            raise ValidationError({
                'translated_config': (
                    'Unsupported translated configuration keys: '
                    + ', '.join(sorted(unsupported_keys))
                )
            })

        canonical_config = question.config or {}
        translated_config = self.translated_config
        if question.question_type == 'rating' and 'labels' in translated_config:
            labels = translated_config['labels']
            canonical_labels = canonical_config.get('labels', {})
            if not isinstance(labels, dict) or not isinstance(canonical_labels, dict):
                raise ValidationError({
                    'translated_config': 'Rating labels must be an object keyed by canonical values.'
                })
            if set(labels) - set(canonical_labels):
                raise ValidationError({
                    'translated_config': 'Rating labels must use canonical rating values.'
                })
            if any(not isinstance(value, str) for value in labels.values()):
                raise ValidationError({
                    'translated_config': 'Translated rating labels must be strings.'
                })

        list_keys = {
            'likert': 'scale',
            'single_choice': 'choices',
            'multiple_choice': 'choices',
        }
        list_key = list_keys.get(question.question_type)
        if list_key and list_key in translated_config:
            translated_values = translated_config[list_key]
            canonical_values = canonical_config.get(list_key, [])
            if (
                not isinstance(translated_values, list)
                or not isinstance(canonical_values, list)
                or len(translated_values) != len(canonical_values)
                or any(not isinstance(value, str) for value in translated_values)
            ):
                raise ValidationError({
                    'translated_config': (
                        f'Translated {list_key} must contain one string per canonical item '
                        'in the same order.'
                    )
                })

        if question.question_type == 'scale' and any(
            not isinstance(value, str) for value in translated_config.values()
        ):
            raise ValidationError({
                'translated_config': 'Translated scale labels must be strings.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.question} ({self.language_code})"
