"""Shared test fixtures.

Tests run against a real PostgreSQL database (``talento_test``) and a real Redis db 15 —
the schema leans on JSONB, native UUIDs and partial ordering semantics that SQLite does not
reproduce, so an in-memory substitute would test a different system than the one we ship.
"""

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from aiogram import Bot as AiogramBot
from aiogram.client.session.base import BaseSession
from aiogram.methods import AnswerCallbackQuery, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://talento:talento@localhost:5432/talento_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("BOT_TOKEN_ENCRYPTION_KEY", "test-encryption-key-for-tests-only!!")
os.environ.setdefault("BASE_URL", "https://test.example.com")

from app.bot.runtime import get_dispatcher  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.core.redis_client import get_redis  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

# NullPool: connections are never held between tests, so nothing can outlive its loop.
test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _schema():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """Truncate between tests so ordering never matters."""
    yield
    async with test_engine.begin() as conn:
        from sqlalchemy import text

        tables = ",".join(t.name for t in reversed(Base.metadata.sorted_tables))
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    redis = get_redis()
    try:
        await redis.flushdb()
    finally:
        await redis.aclose()


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- helpers


async def register(client: AsyncClient, email: str | None = None) -> dict:
    """Register a user and return {'token', 'email', 'headers'}."""
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "sup3rsecret", "full_name": "Test User"},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"token": token, "email": email, "headers": {"Authorization": f"Bearer {token}"}}


async def make_company(client: AsyncClient, name: str = "Acme") -> dict:
    """Register a user, create their company, return auth headers plus ids."""
    user = await register(client)
    resp = await client.post("/api/v1/companies", json={"name": name}, headers=user["headers"])
    assert resp.status_code == 201, resp.text
    company = resp.json()
    return {**user, "company": company, "company_id": company["id"]}


# --------------------------------------------------------------------------- bot harness
# Shared by test_bot_flow and test_multilingual: updates run through the real aiogram
# Dispatcher, with only the network replaced.

CANDIDATE_ID = 424242
BOT_TOKEN = "123456789:AAHfake-token-for-tests"


class FakeSession(BaseSession):
    """Records outgoing Telegram calls instead of performing them."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list = []

    async def close(self) -> None:  # pragma: no cover - nothing to close
        pass

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=len(self.calls),
                date=datetime.now(UTC),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text,
            )
        return True

    async def stream_content(self, *args, **kwargs):  # pragma: no cover
        yield b""

    @property
    def texts(self) -> list[str]:
        return [c.text for c in self.calls if isinstance(c, SendMessage)]

    @property
    def last_text(self) -> str:
        return self.texts[-1] if self.texts else ""

    @property
    def alerts(self) -> list[str]:
        return [c.text for c in self.calls if isinstance(c, AnswerCallbackQuery) and c.text]

    @property
    def buttons(self) -> list[str]:
        """Labels on the most recent keyboard, whichever kind it is."""
        for call in reversed(self.calls):
            markup = getattr(call, "reply_markup", None)
            rows = getattr(markup, "keyboard", None) or getattr(markup, "inline_keyboard", None)
            if rows:
                return [button.text for row in rows for button in row]
        return []

    def clear(self) -> None:
        self.calls.clear()


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def bot(session: FakeSession) -> AiogramBot:
    return AiogramBot(token=BOT_TOKEN, session=session)


async def _seed_default_statuses(db: AsyncSession, company_id: uuid.UUID) -> None:
    """Mirrors what ``POST /companies`` seeds — needed here because these fixtures build
    the company directly rather than through the API."""
    from app.models import DEFAULT_APPLICATION_STAGES, ApplicationStatus

    for index, (system_key, label, translations, notify) in enumerate(DEFAULT_APPLICATION_STAGES):
        db.add(
            ApplicationStatus(
                company_id=company_id,
                system_key=system_key,
                label=label,
                translations=translations,
                notify_candidate=notify,
                sort_order=index,
            )
        )


@pytest_asyncio.fixture
async def tenant():
    """A single-language company with a connected bot and one active vacancy."""
    from app.core.crypto import encrypt
    from app.models import Bot as BotModel
    from app.models import Company, Vacancy

    async with TestSession() as db:
        company = Company(
            name="Acme",
            slug=f"acme-{uuid.uuid4().hex[:6]}",
            billing_mode="unlimited",
            balance_uzs=0,
        )
        db.add(company)
        await db.flush()
        await _seed_default_statuses(db, company.id)

        bot_row = BotModel(
            company_id=company.id,
            token_encrypted=encrypt(BOT_TOKEN),
            bot_username="acme_hr_bot",
            webhook_secret="s3cret",
            language="ru",
        )
        vacancy = Vacancy(
            company_id=company.id, title="Бариста", description="Хорошая работа", status="active"
        )
        db.add_all([bot_row, vacancy])
        await db.commit()
        return {"company_id": company.id, "bot_id": bot_row.id, "vacancy_id": vacancy.id}


async def feed(
    bot: AiogramBot,
    tenant: dict,
    *,
    text: str | None = None,
    data: str | None = None,
    contact=None,
    language_code: str | None = None,
):
    """Push one update through the dispatcher exactly as the webhook would."""
    from app.bot.runtime import load_bot_context

    async with TestSession() as db:
        ctx = await load_bot_context(db, tenant["bot_id"])

    redis = get_redis()
    tg_user = TgUser(
        id=CANDIDATE_ID,
        is_bot=False,
        first_name="Аскар",
        username="askar",
        language_code=language_code,
    )
    chat = Chat(id=CANDIDATE_ID, type="private")

    if data is not None:
        update = Update(
            update_id=1,
            callback_query=CallbackQuery(
                id="cb1",
                from_user=tg_user,
                chat_instance="ci",
                data=data,
                message=Message(message_id=1, date=datetime.now(UTC), chat=chat),
            ),
        )
    else:
        update = Update(
            update_id=1,
            message=Message(
                message_id=1,
                date=datetime.now(UTC),
                chat=chat,
                from_user=tg_user,
                text=text,
                contact=contact,
            ),
        )

    try:
        async with TestSession() as db:
            await get_dispatcher().feed_update(bot, update, ctx=ctx, db=db, redis=redis)
    finally:
        await redis.aclose()


@pytest_asyncio.fixture
async def multi_tenant():
    """A company publishing in ru + uz, with one fully translated vacancy."""
    from app.core.crypto import encrypt
    from app.models import Bot as BotModel
    from app.models import Company, Vacancy

    async with TestSession() as db:
        company = Company(
            name="Acme",
            slug=f"acme-{uuid.uuid4().hex[:6]}",
            billing_mode="unlimited",
            balance_uzs=0,
            default_language="ru",
            enabled_languages=["ru", "uz"],
        )
        db.add(company)
        await db.flush()
        await _seed_default_statuses(db, company.id)

        bot_row = BotModel(
            company_id=company.id,
            token_encrypted=encrypt(BOT_TOKEN),
            bot_username="acme_hr_bot",
            webhook_secret="s3cret",
            language="ru",
            welcome_message="Добро пожаловать!",
            translations={"uz": {"welcome_message": "Xush kelibsiz!"}},
        )
        vacancy = Vacancy(
            company_id=company.id,
            title="Бариста",
            description="Готовим кофе",
            city="Ташкент",
            status="active",
            translations={
                "uz": {"title": "Barista", "description": "Qahva tayyorlaymiz"}
            },
        )
        db.add_all([bot_row, vacancy])
        await db.commit()
        return {
            "company_id": company.id,
            "bot_id": bot_row.id,
            "vacancy_id": vacancy.id,
        }


async def tap(bot: AiogramBot, tenant: dict, label: str, **kwargs):
    """Press a bottom-keyboard button — which Telegram delivers as a plain text message."""
    await feed(bot, tenant, text=label, **kwargs)


async def tap_matching(bot: AiogramBot, tenant: dict, session, needle: str, **kwargs):
    """Press the first button on the current keyboard whose label contains ``needle``."""
    for label in session.buttons:
        if needle in label:
            await tap(bot, tenant, label, **kwargs)
            return label
    raise AssertionError(f"No button containing {needle!r} in {session.buttons}")
