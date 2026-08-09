"""Content localisation.

Two different things are localised in this product, and they work differently:

* **Bot chrome** — button labels, prompts, validation errors. Shipped with the code in
  ``app/bot/texts.py``; a language exists only if we have translated those strings.
* **Company content** — vacancy titles, descriptions, branch names, question wording. Typed
  by the HR in the panel, one tab per language.

This module handles the second kind. Each translatable model keeps its original column as
the **base value** and gains a ``translations`` JSONB map of the shape::

    {"uz": {"title": "Barista", "description": "..."},
     "en": {"title": "Barista", "description": "..."}}

Resolution is ``translations[lang][field]`` falling back to the column. Keeping the column
authoritative for the base language means no data migration, ``ORDER BY title`` and CSV
export keep working on a real column, and a half-translated vacancy degrades to the base
language instead of rendering blank in the bot.
"""

from typing import Any

# Languages we ship bot chrome for. Adding a fourth is a two-step change: add its dict to
# app/bot/texts.py, then add the code here — nothing else needs to know.
SUPPORTED_LANGUAGES: tuple[str, ...] = ("ru", "uz", "en")

LANGUAGE_NAMES: dict[str, str] = {
    "ru": "Русский",
    "uz": "O‘zbekcha",
    "en": "English",
}

DEFAULT_LANGUAGE = "ru"


def normalise(lang: str | None) -> str | None:
    """Map a raw language tag onto a supported code, or None.

    Telegram sends IETF tags like ``ru-RU`` or ``en-GB``; only the primary subtag matters.
    """
    if not lang:
        return None
    primary = lang.split("-")[0].strip().lower()
    return primary if primary in SUPPORTED_LANGUAGES else None


def localized(obj: Any, field: str, lang: str | None) -> Any:
    """Return ``obj.field`` in ``lang``, falling back to the base column.

    An empty or whitespace-only translation counts as missing — an HR who opened a language
    tab and typed nothing should not blank the field for candidates.
    """
    if lang:
        translations = getattr(obj, "translations", None) or {}
        value = (translations.get(lang) or {}).get(field)
        if isinstance(value, str):
            if value.strip():
                return value
        elif value:
            return value
    return getattr(obj, field)


def localized_options(question: Any, lang: str | None) -> list[str]:
    """Choice options in ``lang``.

    Falls back per-list rather than per-item: a translated list with the wrong length would
    silently misalign answers against the base options, so it is rejected wholesale.
    """
    base = question.options or []
    if not lang:
        return base
    translated = (getattr(question, "translations", None) or {}).get(lang, {}).get("options")
    if isinstance(translated, list) and len(translated) == len(base):
        return [
            (t.strip() if isinstance(t, str) and t.strip() else base[i])
            for i, t in enumerate(translated)
        ]
    return base


def base_option_for(question: Any, lang: str | None, index: int) -> str | None:
    """Map a chosen option index back to its base-language value.

    Applications always store the base wording so that HR, CSV export and filters see one
    consistent vocabulary no matter which language the candidate answered in.
    """
    base = question.options or []
    return base[index] if 0 <= index < len(base) else None


def clean_translations(
    translations: dict[str, Any] | None,
    allowed_fields: tuple[str, ...],
    enabled_languages: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Drop unknown languages/fields and empty values before persisting."""
    if not translations:
        return {}
    allowed_langs = set(enabled_languages or SUPPORTED_LANGUAGES) & set(SUPPORTED_LANGUAGES)

    cleaned: dict[str, dict[str, Any]] = {}
    for lang, fields in translations.items():
        if lang not in allowed_langs or not isinstance(fields, dict):
            continue
        entry = {}
        for field, value in fields.items():
            if field not in allowed_fields:
                continue
            if isinstance(value, str):
                if value.strip():
                    entry[field] = value.strip()
            elif isinstance(value, list):
                if value:
                    entry[field] = value
            elif value is not None:
                entry[field] = value
        if entry:
            cleaned[lang] = entry
    return cleaned
