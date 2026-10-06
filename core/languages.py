"""Shared language-code normalization for persisted language choices."""

import re


_LANGUAGE_CODE_PATTERN = re.compile(r'^[a-zA-Z]{2,8}(?:-[a-zA-Z0-9]{1,8})*$')

SUPPORTED_QUESTIONNAIRE_LANGUAGES = (
    {'code': 'en-us', 'name': 'English'},
    {'code': 'fr', 'name': 'French'},
    {'code': 'de', 'name': 'German'},
    {'code': 'it', 'name': 'Italian'},
    {'code': 'es', 'name': 'Spanish'},
    {'code': 'pt', 'name': 'Portuguese'},
    {'code': 'ja', 'name': 'Japanese'},
    {'code': 'zh-hans', 'name': 'Simplified Chinese'},
)


def normalize_language_code(language_code):
    """Return a normalized hyphenated language code, or ``None`` if invalid."""
    if not isinstance(language_code, str):
        return None

    normalized = language_code.strip().replace('_', '-').lower()
    if len(normalized) > 35 or not _LANGUAGE_CODE_PATTERN.fullmatch(normalized):
        return None

    return normalized
