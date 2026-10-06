"""Helpers for managing questionnaire translation languages and completeness."""

from core.languages import (
    SUPPORTED_QUESTIONNAIRE_LANGUAGES,
    normalize_language_code,
)


def supported_language_options():
    """Return stable English labels for supported questionnaire languages."""
    return [
        {'code': language['code'], 'label': language['name']}
        for language in SUPPORTED_QUESTIONNAIRE_LANGUAGES
    ]


def questionnaire_language_name(language_code):
    """Return a stable English name, falling back to the normalized code."""
    normalized_code = normalize_language_code(language_code)
    return next(
        (
            language['name']
            for language in SUPPORTED_QUESTIONNAIRE_LANGUAGES
            if language['code'] == normalized_code
        ),
        normalized_code or language_code,
    )


def available_questionnaire_language_options(questionnaire):
    """List the source language and added, catalogue-supported translations."""
    source_code = normalize_language_code(questionnaire.source_language)
    catalog = supported_language_options()
    catalog_by_code = {language['code']: language for language in catalog}

    source_option = catalog_by_code.get(source_code, {
        'code': source_code or questionnaire.source_language,
        'label': questionnaire_language_name(questionnaire.source_language),
    })
    options = [source_option]

    added_codes = {
        normalized_code
        for translation in questionnaire.translations.all()
        if (normalized_code := normalize_language_code(translation.language_code))
    }
    options.extend(
        language
        for language in catalog
        if language['code'] != source_code and language['code'] in added_codes
    )
    return options


def resolve_questionnaire_language(questionnaire, requested_language):
    """Return a selected language only when it is available for this questionnaire."""
    normalized_language = normalize_language_code(requested_language)
    available_codes = {
        language['code']
        for language in available_questionnaire_language_options(questionnaire)
    }
    if normalized_language in available_codes:
        return normalized_language
    return normalize_language_code(questionnaire.source_language) or questionnaire.source_language


def is_supported_language(language_code, source_language):
    normalized_code = normalize_language_code(language_code)
    if not normalized_code:
        return False
    return any(
        option['code'] == normalized_code
        for option in supported_language_options()
    )


def questionnaire_translation_completeness(questionnaire, language_code):
    """Count populated translated content fields against canonical content fields."""
    questionnaire_translation = questionnaire.translations.filter(
        language_code=language_code
    ).first()

    translated_count = 0
    total_count = 1
    if questionnaire_translation and questionnaire_translation.name.strip():
        translated_count += 1

    if questionnaire.description.strip():
        total_count += 1
        if questionnaire_translation and questionnaire_translation.description.strip():
            translated_count += 1

    sections = questionnaire.sections.prefetch_related('translations', 'questions__translations')
    for section in sections:
        section_translation = next(
            (item for item in section.translations.all() if item.language_code == language_code),
            None,
        )
        if section.title.strip():
            total_count += 1
            if section_translation and section_translation.title.strip():
                translated_count += 1
        if section.description.strip():
            total_count += 1
            if section_translation and section_translation.description.strip():
                translated_count += 1

        for question in section.questions.all():
            question_translation = next(
                (
                    item for item in question.translations.all()
                    if item.language_code == language_code
                ),
                None,
            )
            if question.question_text.strip():
                total_count += 1
                if question_translation and question_translation.question_text.strip():
                    translated_count += 1

            config = question.config or {}
            translated_config = (
                question_translation.translated_config
                if question_translation
                else {}
            )
            if question.question_type == 'rating':
                source_labels = config.get('labels', {})
                translated_labels = translated_config.get('labels', {})
                if isinstance(source_labels, dict):
                    for key, source_label in source_labels.items():
                        if not isinstance(source_label, str) or not source_label.strip():
                            continue
                        total_count += 1
                        translated_label = (
                            translated_labels.get(key)
                            if isinstance(translated_labels, dict)
                            else None
                        )
                        if isinstance(translated_label, str) and translated_label.strip():
                            translated_count += 1
            elif question.question_type in {'likert', 'single_choice', 'multiple_choice'}:
                key = 'scale' if question.question_type == 'likert' else 'choices'
                source_values = config.get(key, [])
                translated_values = translated_config.get(key, [])
                if isinstance(source_values, list):
                    for index, source_value in enumerate(source_values):
                        if not isinstance(source_value, str) or not source_value.strip():
                            continue
                        total_count += 1
                        translated_value = (
                            translated_values[index]
                            if isinstance(translated_values, list)
                            and index < len(translated_values)
                            else None
                        )
                        if isinstance(translated_value, str) and translated_value.strip():
                            translated_count += 1
            elif question.question_type == 'scale':
                for key in ('min_label', 'max_label'):
                    source_label = config.get(key)
                    if not isinstance(source_label, str) or not source_label.strip():
                        continue
                    total_count += 1
                    translated_label = translated_config.get(key)
                    if isinstance(translated_label, str) and translated_label.strip():
                        translated_count += 1

    return {
        'translated_count': translated_count,
        'total_count': total_count,
        'percentage': round(translated_count * 100 / total_count) if total_count else 100,
        'complete': translated_count == total_count,
    }
