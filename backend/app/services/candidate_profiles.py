"""Resolve candidate identity from immutable application answer snapshots."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CandidateProfile:
    name: str
    photo_url: str | None


def resolve_candidate_profile(
    answers: list[dict[str, Any]] | None,
    fallback_name: str | None,
) -> CandidateProfile:
    """Return the configured application name/photo, with Telegram-name fallback.

    Profile roles are copied into ``applications.answers`` when the form is submitted, so
    changing or deleting a question later never changes an existing candidate card or
    notification.
    """
    name = fallback_name or "—"
    photo_url = None

    for answer in answers or []:
        if answer.get("skipped"):
            continue
        if answer.get("profile_field") == "candidate_name":
            value = answer.get("answer")
            if isinstance(value, str) and value.strip():
                name = value.strip()
        elif answer.get("profile_field") == "candidate_photo":
            value = answer.get("file_url")
            if isinstance(value, str) and value.strip():
                photo_url = value.strip()

    return CandidateProfile(name=name, photo_url=photo_url)
