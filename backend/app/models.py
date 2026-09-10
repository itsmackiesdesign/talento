"""SQLAlchemy 2.0 models — mirrors the schema in the spec, §6.

Every tenant-owned table carries ``company_id``. Query helpers in the API layer always
filter on it; see ``app/core/deps.py`` for how the current company is resolved.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


TS = DateTime(timezone=True)
SIGNUP_BONUS_UZS = 20_000


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint(
            "billing_mode IN ('unlimited','pay_per_application')",
            name="ck_company_billing_mode",
        ),
        CheckConstraint("balance_uzs >= 0", name="ck_company_balance_nonnegative"),
        CheckConstraint("application_price_uzs > 0", name="ck_company_application_price_positive"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text)
    default_language: Mapped[str] = mapped_column(String(5), default="ru", nullable=False)
    # Languages the bot offers candidates. Always contains default_language; when it holds
    # a single entry the bot skips the language picker entirely.
    enabled_languages: Mapped[list[str]] = mapped_column(
        JSONB, default=lambda: ["ru"], nullable=False
    )
    # Flipped on automatically when the first active branch appears; can be toggled by hand.
    branches_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    billing_mode: Mapped[str] = mapped_column(
        String(30), default="pay_per_application", nullable=False
    )
    balance_uzs: Mapped[int] = mapped_column(BigInteger, default=SIGNUP_BONUS_UZS, nullable=False)
    application_price_uzs: Mapped[int] = mapped_column(BigInteger, default=2000, nullable=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suspension_reason: Mapped[str | None] = mapped_column(Text)
    suspended_at: Mapped[datetime | None] = mapped_column(TS)
    suspended_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # The platform service bot posts one notification per application to this tenant-owned
    # Telegram group. Negative IDs are normal for groups/supergroups.
    notification_chat_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    notification_chat_title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    members: Mapped[list["CompanyMember"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    bot: Mapped["Bot | None"] = relationship(
        back_populates="company", cascade="all, delete-orphan", uselist=False
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    # Set once the HR links their Telegram to the platform bot via /link {code}.
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    # Platform administrators are intentionally independent of tenant memberships/roles.
    # The flag can only be granted through the local admin CLI or direct database access.
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    memberships: Mapped[list["CompanyMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class CompanyMember(Base):
    __tablename__ = "company_members"
    __table_args__ = (CheckConstraint("role IN ('owner','member')", name="ck_member_role"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    company: Mapped[Company] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class TeamInvitation(Base):
    __tablename__ = "team_invitations"
    __table_args__ = (
        CheckConstraint("role IN ('member')", name="ck_team_invitation_role"),
        Index("ix_team_invitations_company_email", "company_id", "email"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)
    # Only SHA-256 is persisted. Possession of the raw token grants membership, so a
    # database read must not be enough to reconstruct an invitation URL.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    expires_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(TS)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)


class Bot(Base):
    __tablename__ = "bots"

    id: Mapped[uuid.UUID] = _uuid_pk()
    # MVP: exactly one bot per company.
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    bot_username: Mapped[str] = mapped_column(Text, nullable=False)
    webhook_secret: Mapped[str] = mapped_column(Text, nullable=False)
    welcome_message: Mapped[str | None] = mapped_column(Text)
    about_text: Mapped[str | None] = mapped_column(Text)
    after_apply_message: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(5), default="ru", nullable=False)
    contacts_text: Mapped[str | None] = mapped_column(Text)
    # {lang: {welcome_message, about_text, after_apply_message, contacts_text}}
    # — see app/core/i18n.py
    translations: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=dict)
    notify_candidate_on_status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    company: Mapped[Company] = relationship(back_populates="bot")


class TelegramUpdateInbox(Base):
    """Durable, idempotent hand-off between Telegram and the async worker.

    Telegram retries a webhook until it receives ``200``. A unique dedupe key lets us
    acknowledge only after PostgreSQL has the update, while the worker can safely receive
    duplicate jobs without running the candidate flow twice.
    """

    __tablename__ = "telegram_update_inbox"
    __table_args__ = (
        CheckConstraint(
            "source IN ('tenant','platform')", name="ck_telegram_inbox_source"
        ),
        CheckConstraint(
            "status IN ('pending','processing','processed','failed')",
            name="ck_telegram_inbox_status",
        ),
        Index("ix_telegram_inbox_status_available", "status", "available_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    # ``NULL`` is valid for the platform service bot. ``dedupe_key`` deliberately carries
    # the source too, because PostgreSQL unique constraints consider multiple NULLs distinct.
    bot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bots.id", ondelete="CASCADE")
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    update_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # The complete payload is needed only until processing succeeds; the worker clears it
    # afterwards, retaining just safe delivery metadata for observability and dedupe.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    available_at: Mapped[datetime] = mapped_column(
        TS, server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(TS)
    created_at: Mapped[datetime] = mapped_column(
        TS, server_default=func.now(), nullable=False
    )


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (Index("ix_branches_company", "company_id", "sort_order"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(Text)
    # Sent as a Telegram location pin on the branch card. Both or neither.
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # {lang: {name, city, address}}
    translations: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    vacancies: Mapped[list["Vacancy"]] = relationship(back_populates="branch")


class Vacancy(Base):
    __tablename__ = "vacancies"
    __table_args__ = (
        CheckConstraint("status IN ('draft','active','archived')", name="ck_vacancy_status"),
        Index("ix_vacancies_company_status", "company_id", "status", "sort_order"),
        Index("ix_vacancies_company_hot", "company_id", "is_hot", "status"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    # NULL = a general vacancy (shown under "🌐 Общие вакансии"), or company has no branches.
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    city: Mapped[str | None] = mapped_column(Text)
    employment_type: Mapped[str | None] = mapped_column(String(30))
    salary_from: Mapped[int | None] = mapped_column(Integer)
    salary_to: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(10), default="UZS", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    # Listed under "🔥 Current openings" — a flat, branch-independent shortlist. A vacancy
    # can be both featured and attached to a branch, so it appears in both places.
    is_hot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    photo_url: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # {lang: {title, description, city, employment_type}}
    translations: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    branch: Mapped[Branch | None] = relationship(back_populates="vacancies")
    campaigns: Mapped[list["RecruitmentCampaign"]] = relationship(
        back_populates="vacancy", cascade="all, delete-orphan"
    )
    questions: Mapped[list["Question"]] = relationship(
        back_populates="vacancy", cascade="all, delete-orphan"
    )


QUESTION_TYPES = (
    "short_text",
    "long_text",
    "single_choice",
    "multi_choice",
    "number",
    "phone",
    "file",
    "datetime",
)


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint(
            "type IN ('short_text','long_text','single_choice','multi_choice',"
            "'number','phone','file','datetime')",
            name="ck_question_type",
        ),
        CheckConstraint(
            "profile_field IS NULL OR profile_field IN ('candidate_name','candidate_photo')",
            name="ck_question_profile_field",
        ),
        Index("ix_questions_company_vacancy", "company_id", "vacancy_id", "sort_order"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    # NULL = company-wide question, asked for every vacancy before vacancy-specific ones.
    vacancy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vacancies.id", ondelete="CASCADE")
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    options: Mapped[list[str] | None] = mapped_column(JSONB)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_filterable: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    profile_field: Mapped[str | None] = mapped_column(String(30))
    validation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # {lang: {text, options}} — a translated options list must match the base length,
    # otherwise it is ignored so answer indexes can never misalign.
    translations: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    vacancy: Mapped[Vacancy | None] = relationship(back_populates="questions")


class News(Base):
    """Company announcements shown under the bot's "📰 News" menu item."""

    __tablename__ = "news"
    __table_args__ = (Index("ix_news_company", "company_id", "sort_order"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    photo_url: Mapped[str | None] = mapped_column(Text)
    link_url: Mapped[str | None] = mapped_column(Text)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # {lang: {title, content}}
    translations: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "telegram_user_id", name="uq_candidate_company_telegram"
        ),
        UniqueConstraint("id", "company_id", name="uq_candidate_id_company"),
        Index("ix_candidates_company_created", "company_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_username: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str] = mapped_column(Text, default="", nullable=False)
    phone: Mapped[str | None] = mapped_column(Text)
    # Durable copy of the candidate's chosen bot language; Redis holds the hot value.
    language: Mapped[str | None] = mapped_column(String(5))
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)


# The three stages every company starts with and can never delete — see ApplicationStatus.
SYSTEM_STATUS_KEYS = ("new", "hired", "rejected")

# Seeded once per company on creation (companies.py) — order here becomes initial sort_order.
# notify_candidate mirrors what used to be a hardcoded NOTIFIABLE set in workers/tasks.py.
# (system_key, ru label, {lang: {label}} translations, notify_candidate, color)
DEFAULT_APPLICATION_STAGES: tuple[tuple[str | None, str, dict[str, Any], bool, str], ...] = (
    ("new", "Новая", {"uz": {"label": "Yangi"}, "en": {"label": "New"}}, False, "#3b82f6"),
    (
        None,
        "Просмотрена",
        {"uz": {"label": "Ko‘rilgan"}, "en": {"label": "Viewed"}},
        False,
        "#8b5cf6",
    ),
    (
        None,
        "Интервью",
        {"uz": {"label": "Suhbat"}, "en": {"label": "Interview"}},
        True,
        "#f59e0b",
    ),
    (None, "Оффер", {"uz": {"label": "Taklif"}, "en": {"label": "Offer"}}, True, "#06b6d4"),
    (
        "hired",
        "Принят",
        {"uz": {"label": "Qabul qilingan"}, "en": {"label": "Hired"}},
        True,
        "#10b981",
    ),
    (
        "rejected",
        "Отклонена",
        {"uz": {"label": "Rad etilgan"}, "en": {"label": "Rejected"}},
        True,
        "#ef4444",
    ),
)


class ApplicationStatus(Base):
    """A company's own kanban pipeline stage.

    ``new`` / ``hired`` / ``rejected`` are seeded for every company (see ``companies.py`` and
    the ``application_pipeline_stages`` migration) with ``system_key`` set and are otherwise
    ordinary rows — the *API* refuses to rename, delete or reorder them (only their display
    color is editable), not a DB constraint, so the check lives in
    ``app/api/application_statuses.py``.
    Everything else is a step the HR created, freely editable, deletable (once no application
    still sits in it) and reorderable among themselves.
    """

    __tablename__ = "application_statuses"
    __table_args__ = (
        # NULLs are distinct in Postgres, so this only constrains the system rows — a
        # company can still have any number of custom (system_key IS NULL) statuses.
        UniqueConstraint("company_id", "system_key", name="uq_status_company_system_key"),
        CheckConstraint("color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_application_status_color"),
        Index("ix_application_statuses_company_sort", "company_id", "sort_order"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    system_key: Mapped[str | None] = mapped_column(String(20))
    label: Mapped[str] = mapped_column(Text, nullable=False)
    # {lang: {label}}
    translations: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=dict)
    # Whether moving an application into this step messages the candidate. Defaults off for
    # 'new' (that's application creation, not a transition) and on for everything else.
    notify_candidate: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    color: Mapped[str] = mapped_column(
        String(7), default="#3b82f6", server_default="#3b82f6", nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    @property
    def is_system(self) -> bool:
        return self.system_key is not None


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        # One active application per candidate per vacancy.
        UniqueConstraint("vacancy_id", "candidate_id", name="uq_application_vacancy_candidate"),
        ForeignKeyConstraint(
            ["candidate_id", "company_id"],
            ["candidates.id", "candidates.company_id"],
            name="fk_application_candidate_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["campaign_id", "company_id"],
            ["recruitment_campaigns.id", "recruitment_campaigns.company_id"],
            name="fk_application_campaign_company",
        ),
        Index("ix_applications_company_created", "company_id", "created_at"),
        Index("ix_applications_campaign", "company_id", "campaign_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    # No ondelete: a status with applications still in it must be rejected by the API
    # before it can be deleted (reassign first) — this FK is the last-resort backstop.
    status_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("application_statuses.id"), nullable=False
    )
    # Snapshot: [{question_id, question_text, type, answer}] — kept verbatim so later edits
    # to the question set never rewrite history.
    answers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    # Immutable contact snapshot. The scoped Candidate row may be refreshed when the same
    # Telegram user applies again, but an existing application must keep the identity and
    # contact data the recruiter actually received at submission time.
    candidate_name: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    candidate_username: Mapped[str | None] = mapped_column(Text)
    candidate_phone: Mapped[str | None] = mapped_column(Text)
    candidate_language: Mapped[str | None] = mapped_column(String(5))
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    vacancy: Mapped[Vacancy] = relationship()
    candidate: Mapped[Candidate] = relationship()
    status: Mapped[ApplicationStatus] = relationship()
    comments: Mapped[list["ApplicationComment"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    history: Mapped[list["ApplicationStatusHistory"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["ApplicationTask"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    interviews: Mapped[list["ApplicationInterview"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    campaign: Mapped["RecruitmentCampaign | None"] = relationship(overlaps="candidate")


class RecruitmentCampaign(Base):
    """A Telegram acquisition source bound to one vacancy and tenant."""

    __tablename__ = "recruitment_campaigns"
    __table_args__ = (
        UniqueConstraint("code", name="uq_recruitment_campaign_code"),
        UniqueConstraint("id", "company_id", name="uq_recruitment_campaign_company"),
        Index("ix_recruitment_campaigns_company_vacancy", "company_id", "vacancy_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source: Mapped[str | None] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(24), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    vacancy: Mapped[Vacancy] = relationship(back_populates="campaigns")


class ApplicationComment(Base):
    __tablename__ = "application_comments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    application: Mapped[Application] = relationship(back_populates="comments")
    user: Mapped[User] = relationship()


class ApplicationTask(Base):
    """A small, explicit next action for the recruiter-facing candidate workspace."""

    __tablename__ = "application_tasks"
    __table_args__ = (
        Index("ix_application_tasks_due", "application_id", "completed_at", "due_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(TS)
    completed_at: Mapped[datetime | None] = mapped_column(TS)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    application: Mapped[Application] = relationship(back_populates="tasks")


class ApplicationInterview(Base):
    """A planned interview owned by the candidate application, not an external calendar."""

    __tablename__ = "application_interviews"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('video', 'in_person', 'phone')", name="ck_application_interview_kind"
        ),
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled')",
            name="ck_application_interview_status",
        ),
        Index("ix_application_interviews_schedule", "application_id", "status", "scheduled_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="video")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")
    scheduled_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=45)
    location: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    application: Mapped[Application] = relationship(back_populates="interviews")
    scorecard: Mapped["ApplicationInterviewScorecard | None"] = relationship(
        back_populates="interview", uselist=False, cascade="all, delete-orphan"
    )


class ApplicationInterviewScorecard(Base):
    """An immutable recruiter assessment recorded after a completed interview."""

    __tablename__ = "application_interview_scorecards"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_interview_scorecard_rating"),
        CheckConstraint(
            "recommendation IN ('strong_yes', 'yes', 'no', 'strong_no')",
            name="ck_interview_scorecard_recommendation",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    interview_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("application_interviews.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(20), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    interview: Mapped[ApplicationInterview] = relationship(back_populates="scorecard")


class ApplicationStatusHistory(Base):
    __tablename__ = "application_status_history"

    id: Mapped[uuid.UUID] = _uuid_pk()
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    # Nullable + SET NULL: a deleted status must not drag its history away, or block its own
    # deletion. The label is snapshotted separately below so the record stays readable even
    # once the id it pointed to is gone — same reasoning as QuestionSnapshot.base_text.
    from_status_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("application_statuses.id", ondelete="SET NULL")
    )
    to_status_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("application_statuses.id", ondelete="SET NULL")
    )
    from_status_label: Mapped[str | None] = mapped_column(Text)
    to_status_label: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional recruiter context is an immutable part of the transition, not a mutable
    # comment. It keeps hand-offs and rejection decisions understandable in the timeline.
    reason: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    application: Mapped[Application] = relationship(back_populates="history")
    user: Mapped[User | None] = relationship()


class AdminAuditLog(Base):
    """Immutable record of every platform-admin mutation."""

    __tablename__ = "admin_audit_logs"
    __table_args__ = (Index("ix_admin_audit_created", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    target_company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    actor: Mapped[User] = relationship()
    target_company: Mapped[Company | None] = relationship(foreign_keys=[target_company_id])


class BalanceTransaction(Base):
    """Append-only UZS ledger for tenant balance changes."""

    __tablename__ = "balance_transactions"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('signup_bonus','top_up','application_charge')",
            name="ck_balance_transaction_kind",
        ),
        CheckConstraint("amount_uzs <> 0", name="ck_balance_transaction_nonzero"),
        CheckConstraint("balance_after_uzs >= 0", name="ck_balance_after_nonnegative"),
        Index("ix_balance_transactions_company_created", "company_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    amount_uzs: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after_uzs: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), unique=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)

    company: Mapped[Company] = relationship()
    application: Mapped[Application | None] = relationship()
    created_by: Mapped[User | None] = relationship()
