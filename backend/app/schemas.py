"""Pydantic request/response schemas."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Language = Literal["ru", "uz", "en"]
VacancyStatus = Literal["draft", "active", "archived"]
QuestionType = Literal[
    "short_text", "long_text", "single_choice", "multi_choice", "number", "phone", "file",
    "datetime",
]
DatetimeMask = Literal["date", "datetime", "time"]
QuestionProfileField = Literal["candidate_name", "candidate_photo"]
BillingMode = Literal["unlimited", "pay_per_application"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# {lang: {field: value}} — see app/core/i18n.py for how these resolve at read time.
Translations = dict[str, dict[str, Any]]


# --------------------------------------------------------------------------- auth


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=128)]
    full_name: Annotated[str, Field(min_length=1, max_length=120)]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    telegram_user_id: int | None = None
    is_platform_admin: bool = False
    created_at: datetime


class MembershipOut(ORMModel):
    company_id: uuid.UUID
    role: str


class MeOut(BaseModel):
    user: UserOut
    companies: list["CompanyOut"]
    role: str | None = None


# --------------------------------------------------------------------------- company


class CompanyCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    default_language: Language = "ru"


class CompanyUpdate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    logo_url: str | None = None
    default_language: Language | None = None
    branches_enabled: bool | None = None
    enabled_languages: list[Language] | None = None

    @field_validator("enabled_languages")
    @classmethod
    def dedupe_languages(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        # Order is meaningful — it drives the language picker in the bot.
        seen: list[str] = []
        for lang in v:
            if lang not in seen:
                seen.append(lang)
        if not seen:
            raise ValueError("At least one language must stay enabled")
        return seen


class CompanyOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None
    default_language: str
    enabled_languages: list[str]
    branches_enabled: bool
    billing_mode: BillingMode
    balance_uzs: int
    application_price_uzs: int
    is_suspended: bool
    suspension_reason: str | None
    suspended_at: datetime | None
    created_at: datetime


class TeamMemberOut(BaseModel):
    user_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    telegram_linked: bool
    joined_at: datetime


class TeamInvitationCreate(BaseModel):
    email: EmailStr


class TeamInvitationOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: Literal["member"]
    expires_at: datetime
    created_at: datetime


class TeamInvitationCreatedOut(TeamInvitationOut):
    invite_url: str


class TeamInvitationPreviewOut(BaseModel):
    company_name: str
    email: EmailStr
    expires_at: datetime


class TeamInvitationAcceptOut(BaseModel):
    company_id: uuid.UUID
    company_name: str
    role: Literal["member"]


# --------------------------------------------------------------------------- platform admin


class AdminStatsOut(BaseModel):
    companies_total: int
    companies_active: int
    companies_suspended: int
    users_total: int
    bots_active: int
    applications_total: int


class AdminCompanyItem(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    billing_mode: BillingMode
    balance_uzs: int
    application_price_uzs: int
    is_suspended: bool
    suspension_reason: str | None
    owner_email: EmailStr | None
    bot_username: str | None
    members_count: int
    vacancies_count: int
    applications_count: int
    created_at: datetime


class AdminCompanyPage(BaseModel):
    items: list[AdminCompanyItem]
    total: int
    page: int
    page_size: int


class AdminCompanyMemberOut(BaseModel):
    user_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    created_at: datetime


class AdminAuditOut(BaseModel):
    id: uuid.UUID
    actor_email: EmailStr
    target_company_id: uuid.UUID | None
    target_company_name: str | None
    action: str
    details: dict[str, Any]
    created_at: datetime


class AdminCompanyDetail(AdminCompanyItem):
    logo_url: str | None
    default_language: str
    enabled_languages: list[str]
    branches_count: int
    members: list[AdminCompanyMemberOut]
    recent_audit: list[AdminAuditOut]


class AdminCompanyUpdate(BaseModel):
    billing_mode: BillingMode | None = None
    application_price_uzs: Annotated[int | None, Field(ge=1, le=1_000_000_000)] = None
    is_suspended: bool | None = None
    suspension_reason: Annotated[str | None, Field(max_length=500)] = None

    @model_validator(mode="after")
    def suspension_requires_reason(self):
        if self.is_suspended is True and not (self.suspension_reason or "").strip():
            raise ValueError("A suspension reason is required")
        return self


class BalanceTopUpRequest(BaseModel):
    amount_uzs: Annotated[int, Field(ge=1, le=10_000_000_000)]
    description: Annotated[str | None, Field(max_length=500)] = None


class BalanceTransactionOut(BaseModel):
    id: uuid.UUID
    amount_uzs: int
    balance_after_uzs: int
    kind: Literal["signup_bonus", "top_up", "application_charge"]
    description: str | None
    application_id: uuid.UUID | None
    vacancy_title: str | None
    created_by_email: EmailStr | None
    created_at: datetime


class BalanceTransactionPage(BaseModel):
    items: list[BalanceTransactionOut]
    total: int
    page: int
    page_size: int


class BillingSummaryOut(BaseModel):
    billing_mode: BillingMode
    balance_uzs: int
    application_price_uzs: int
    remaining_applications: int | None


# --------------------------------------------------------------------------- bot


class BotConnect(BaseModel):
    token: Annotated[str, Field(min_length=20, max_length=200)]

    @field_validator("token")
    @classmethod
    def looks_like_a_bot_token(cls, v: str) -> str:
        v = v.strip()
        if ":" not in v or not v.split(":", 1)[0].isdigit():
            raise ValueError("Token must look like 123456789:AA... — copy it from @BotFather")
        return v


class BotUpdate(BaseModel):
    welcome_message: str | None = None
    about_text: str | None = None
    after_apply_message: str | None = None
    contacts_text: str | None = None
    translations: Translations | None = None
    language: Language | None = None
    notify_candidate_on_status: bool | None = None
    is_active: bool | None = None


class BotOut(ORMModel):
    id: uuid.UUID
    bot_username: str
    welcome_message: str | None
    about_text: str | None
    after_apply_message: str | None
    contacts_text: str | None
    translations: Translations = {}
    language: str
    notify_candidate_on_status: bool
    is_active: bool
    created_at: datetime
    token_hint: str = ""
    webhook_url: str = ""


# --------------------------------------------------------------------------- branches


class BranchCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    city: str | None = None
    address: str | None = None
    photo_url: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_active: bool = True
    translations: Translations | None = None

    @model_validator(mode="after")
    def coordinates_come_in_pairs(self):
        """A lone latitude cannot place a pin, so require both or neither."""
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude, or neither")
        return self



class BranchUpdate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    city: str | None = None
    address: str | None = None
    photo_url: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_active: bool | None = None
    translations: Translations | None = None


class BranchOut(ORMModel):
    id: uuid.UUID
    name: str
    city: str | None
    address: str | None
    photo_url: str | None
    latitude: float | None
    longitude: float | None
    translations: Translations = {}
    is_active: bool
    sort_order: int
    created_at: datetime
    active_vacancy_count: int = 0


class ReorderRequest(BaseModel):
    """Full ordered list of ids; index in the list becomes sort_order."""

    ids: list[uuid.UUID]


# --------------------------------------------------------------------------- vacancies


class VacancyBase(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    description: str = ""
    city: str | None = None
    employment_type: str | None = None
    salary_from: int | None = Field(default=None, ge=0)
    salary_to: int | None = Field(default=None, ge=0)
    currency: str = "UZS"
    status: VacancyStatus = "draft"
    is_hot: bool = False
    photo_url: str | None = None
    branch_id: uuid.UUID | None = None
    translations: Translations | None = None

    @model_validator(mode="after")
    def salary_range_is_ordered(self):
        if self.salary_from is not None and self.salary_to is not None:
            if self.salary_from > self.salary_to:
                raise ValueError("salary_from must not exceed salary_to")
        return self


class VacancyCreate(VacancyBase):
    pass


class VacancyUpdate(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    description: str | None = None
    city: str | None = None
    employment_type: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    currency: str | None = None
    status: VacancyStatus | None = None
    is_hot: bool | None = None
    photo_url: str | None = None
    branch_id: uuid.UUID | None = None
    translations: Translations | None = None
    # Distinguishes "don't touch branch_id" from "set it to NULL".
    clear_branch: bool = False


class VacancyOut(ORMModel):
    id: uuid.UUID
    branch_id: uuid.UUID | None
    branch_name: str | None = None
    title: str
    description: str
    city: str | None
    employment_type: str | None
    salary_from: int | None
    salary_to: int | None
    currency: str
    status: str
    is_hot: bool
    photo_url: str | None
    sort_order: int
    translations: Translations = {}
    created_at: datetime
    application_count: int = 0
    deep_link: str | None = None


class VacancyDuplicate(BaseModel):
    branch_id: uuid.UUID | None = None
    title: str | None = None


# --------------------------------------------------------------------------- questions


class QuestionBase(BaseModel):
    # Multiline and formatted, so roomier than a label — but well inside Telegram's 4096
    # character message limit even after Markdown expands into HTML tags.
    text: Annotated[str, Field(min_length=1, max_length=1500)]
    type: QuestionType
    options: list[str] | None = None
    is_required: bool = True
    is_filterable: bool = False
    profile_field: QuestionProfileField | None = None
    validation: dict[str, Any] | None = None
    translations: Translations | None = None
    vacancy_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def check_type_specific_fields(self):
        if self.type in ("single_choice", "multi_choice"):
            opts = [o.strip() for o in (self.options or []) if o and o.strip()]
            if not 2 <= len(opts) <= 10:
                raise ValueError("Choice questions need between 2 and 10 non-empty options")
            self.options = opts
        else:
            self.options = None
            self.is_filterable = False

        expected_profile_type = {
            "candidate_name": "short_text",
            "candidate_photo": "file",
        }
        if self.profile_field and self.type != expected_profile_type[self.profile_field]:
            raise ValueError(
                f"profile_field '{self.profile_field}' requires question type "
                f"'{expected_profile_type[self.profile_field]}'"
            )

        if self.type == "number":
            if self.validation:
                lo, hi = self.validation.get("min"), self.validation.get("max")
                if lo is not None and hi is not None and lo > hi:
                    raise ValueError("validation.min must not exceed validation.max")
        elif self.type == "datetime":
            # A mask is not optional here: the bot needs to know which of the three
            # formats to parse a candidate's answer against, and the panel always sends
            # one — defaulting keeps direct API callers working without it too.
            mask = (self.validation or {}).get("mask", "date")
            if mask not in ("date", "datetime", "time"):
                raise ValueError("validation.mask must be one of: date, datetime, time")
            self.validation = {"mask": mask}
        else:
            self.validation = None
        return self


class QuestionCreate(QuestionBase):
    pass


class QuestionCopy(BaseModel):
    # None copies into the company-wide set; a UUID copies into that vacancy's own questions.
    vacancy_id: uuid.UUID | None = None


class QuestionUpdate(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=1500)] | None = None
    type: QuestionType | None = None
    options: list[str] | None = None
    is_required: bool | None = None
    is_filterable: bool | None = None
    profile_field: QuestionProfileField | None = None
    validation: dict[str, Any] | None = None
    translations: Translations | None = None


class QuestionOut(ORMModel):
    id: uuid.UUID
    vacancy_id: uuid.UUID | None
    text: str
    type: str
    options: list[str] | None
    is_required: bool
    is_filterable: bool
    profile_field: QuestionProfileField | None
    validation: dict[str, Any] | None
    translations: Translations = {}
    sort_order: int


# --------------------------------------------------------------------------- news


class NewsBase(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    content: str = ""
    photo_url: str | None = None
    link_url: str | None = None
    is_published: bool = True
    translations: Translations | None = None


class NewsCreate(NewsBase):
    pass


class NewsUpdate(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    content: str | None = None
    photo_url: str | None = None
    link_url: str | None = None
    is_published: bool | None = None
    translations: Translations | None = None


class NewsOut(ORMModel):
    id: uuid.UUID
    title: str
    content: str
    photo_url: str | None
    link_url: str | None
    is_published: bool
    sort_order: int
    translations: Translations = {}
    created_at: datetime


# --------------------------------------------------------------------------- applications


class CandidateOut(ORMModel):
    id: uuid.UUID
    telegram_user_id: int
    telegram_username: str | None
    first_name: str
    phone: str | None


class CommentOut(BaseModel):
    id: uuid.UUID
    text: str
    author_name: str
    created_at: datetime


class CommentCreate(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=4000)]


class StatusHistoryOut(BaseModel):
    # Snapshotted at the time of the transition, not a live lookup — see
    # ApplicationStatusHistory in app/models.py. Stays readable even after the status
    # itself is later renamed or deleted.
    from_status_label: str | None
    to_status_label: str
    changed_by_name: str | None
    created_at: datetime


class ApplicationListItem(BaseModel):
    id: uuid.UUID
    status_id: uuid.UUID
    created_at: datetime
    vacancy_id: uuid.UUID
    vacancy_title: str
    branch_id: uuid.UUID | None
    branch_name: str | None
    candidate_name: str
    candidate_photo_url: str | None
    candidate_username: str | None
    candidate_phone: str | None


class ApplicationDetail(ApplicationListItem):
    answers: list[dict[str, Any]]
    comments: list[CommentOut]
    history: list[StatusHistoryOut]


class ApplicationPage(BaseModel):
    items: list[ApplicationListItem]
    total: int
    page: int
    page_size: int


class StatusUpdate(BaseModel):
    status_id: uuid.UUID


# --------------------------------------------------------------------------- application statuses


class ApplicationStatusCreate(BaseModel):
    label: Annotated[str, Field(min_length=1, max_length=60)]
    translations: Translations | None = None
    notify_candidate: bool = True


class ApplicationStatusUpdate(BaseModel):
    label: Annotated[str, Field(min_length=1, max_length=60)] | None = None
    translations: Translations | None = None
    notify_candidate: bool | None = None


class ApplicationStatusOut(ORMModel):
    id: uuid.UUID
    label: str
    translations: Translations = {}
    notify_candidate: bool
    is_system: bool
    sort_order: int
    application_count: int = 0


# --------------------------------------------------------------------------- dashboard


class VacancyStat(BaseModel):
    vacancy_id: uuid.UUID
    title: str
    count: int


class BranchStat(BaseModel):
    branch_id: uuid.UUID | None
    name: str
    count: int


class DailyPoint(BaseModel):
    date: str
    count: int


class DashboardStats(BaseModel):
    applications_7d: int
    applications_30d: int
    applications_total: int
    active_vacancies: int
    by_status: dict[str, int]
    by_vacancy: list[VacancyStat]
    by_branch: list[BranchStat]
    daily: list[DailyPoint]


# --------------------------------------------------------------------------- notifications


class LinkCodeOut(BaseModel):
    code: str
    expires_in: int
    bot_username: str
    deep_link: str | None = None


MeOut.model_rebuild()
