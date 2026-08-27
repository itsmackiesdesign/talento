"""Candidate dialog state, stored in Redis under ``fsm:{bot_id}:{tg_user_id}`` with a 24h TTL.

The spec allows either a ``dialog_states`` table or Redis; Redis wins here because this state
is short-lived, written on every single keystroke of a form, and worthless after expiry —
none of which justifies the write amplification of a Postgres row per candidate.

Note what gets snapshotted: not just ``question_ids`` but the full question payload (text,
type, options, validation). Freezing ids alone still leaves the form broken if HR *deletes*
a question mid-fill; freezing the content means an in-flight candidate finishes the form
they started, no matter what the panel does underneath.
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from redis.asyncio import Redis

from app.core.config import settings

STATE_FILLING = "filling_form"
STATE_CONFIRMING = "confirming"


@dataclass
class QuestionSnapshot:
    """One question, frozen at form start in the candidate's language.

    Each translated field is stored twice: the ``*_display`` value the candidate sees, and
    the base-language value written into ``applications.answers``. HR must read one
    consistent vocabulary in the panel and in CSV exports no matter which language the
    candidate answered in.
    """

    id: str
    text: str
    type: str
    options: list[str] | None = None
    is_required: bool = True
    validation: dict[str, Any] | None = None
    profile_field: str | None = None
    base_text: str | None = None
    base_options: list[str] | None = None

    def canonical_text(self) -> str:
        return self.base_text or self.text

    def canonical_option(self, index: int) -> str | None:
        source = self.base_options or self.options or []
        return source[index] if 0 <= index < len(source) else None


@dataclass
class FormState:
    vacancy_id: str
    questions: list[QuestionSnapshot] = field(default_factory=list)
    current_index: int = 0
    # question_id -> {"value": <canonical value>, "raw": <original>, "skipped": bool}
    answers: dict[str, Any] = field(default_factory=dict)
    # Staging area for multi_choice toggles before "Done" is pressed. Holds option
    # *indexes*, not text, so a selection survives translation into any language.
    pending: list[int] = field(default_factory=list)
    state: str = STATE_FILLING
    lang: str | None = None

    @property
    def total(self) -> int:
        return len(self.questions)

    @property
    def current(self) -> QuestionSnapshot | None:
        if 0 <= self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return None

    def to_json(self) -> str:
        data = asdict(self)
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "FormState":
        data = json.loads(raw)
        questions = [QuestionSnapshot(**q) for q in data.pop("questions", [])]
        return cls(questions=questions, **data)


def _key(bot_id: uuid.UUID | str, tg_user_id: int) -> str:
    return f"fsm:{bot_id}:{tg_user_id}"


async def load(redis: Redis, bot_id: uuid.UUID | str, tg_user_id: int) -> FormState | None:
    raw = await redis.get(_key(bot_id, tg_user_id))
    if not raw:
        return None
    try:
        return FormState.from_json(raw)
    except (ValueError, TypeError):
        # A stale shape from a previous deploy: drop it rather than trapping the candidate.
        await clear(redis, bot_id, tg_user_id)
        return None


async def save(
    redis: Redis, bot_id: uuid.UUID | str, tg_user_id: int, state: FormState
) -> None:
    await redis.set(_key(bot_id, tg_user_id), state.to_json(), ex=settings.FSM_TTL_SECONDS)


async def clear(redis: Redis, bot_id: uuid.UUID | str, tg_user_id: int) -> None:
    await redis.delete(_key(bot_id, tg_user_id))
