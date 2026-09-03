"""Resolve candidate identity from immutable application answer snapshots."""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CandidateProfile:
    name: str
    photo_url: str | None


def resolve_candidate_profile(
    answers: list[dict[str, Any]] | None,
    fallback_name: str | None,
    current_profile_fields: Mapping[str, str] | None = None,
    enabled_profile_fields: Collection[str] | None = None,
    legacy_file_urls: Mapping[str, str] | None = None,
) -> CandidateProfile:
    """Return the configured application name/photo.

    New snapshots carry their profile role themselves and therefore stay immutable. Older
    snapshots predate that field, so they may fall back to the question's current role by
    id. If a profile role is configured but an old application never answered that
    question, using its Telegram identity would be misleading; return a neutral value.
    """
    current_profile_fields = current_profile_fields or {}
    legacy_file_urls = legacy_file_urls or {}
    configured = set(enabled_profile_fields or current_profile_fields.values())
    configured.update(
        str(answer.get("profile_field")) for answer in answers or [] if answer.get("profile_field")
    )

    name = "—" if "candidate_name" in configured else (fallback_name or "—")
    photo_url = None

    for answer in answers or []:
        if answer.get("skipped"):
            continue
        question_id = str(answer.get("question_id") or "").replace("-", "")
        profile_field = answer.get("profile_field") or current_profile_fields.get(question_id)
        if profile_field == "candidate_name":
            value = answer.get("answer")
            if isinstance(value, str) and value.strip():
                name = value.strip()
        elif profile_field == "candidate_photo":
            value = answer.get("file_url")
            if not value and isinstance(answer.get("answer"), str):
                value = legacy_file_urls.get(answer["answer"])
            if isinstance(value, str) and value.strip():
                photo_url = value.strip()

    return CandidateProfile(name=name, photo_url=photo_url)
