"""Tenant-safe audience resolution for vacancy notification campaigns."""

import uuid

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Application,
    ApplicationStatus,
    ApplicationStatusHistory,
    Candidate,
    CompanyCandidate,
    Vacancy,
)
from app.schemas import VacancyCampaignTarget


def _uuid_strings(values: list[uuid.UUID]) -> list[str]:
    return [str(value) for value in values]


async def validate_campaign_target(
    db: AsyncSession,
    company_id: uuid.UUID,
    target: VacancyCampaignTarget,
) -> None:
    """Reject foreign or missing filter ids instead of silently broadening the audience."""

    checks = (
        (Vacancy, target.source_vacancy_ids, "source vacancies"),
        (ApplicationStatus, target.source_status_ids, "application statuses"),
    )
    for model, ids, label in checks:
        if not ids:
            continue
        owned = set(
            await db.scalars(
                select(model.id).where(model.company_id == company_id, model.id.in_(ids))
            )
        )
        if owned != set(ids):
            raise ValueError(f"One or more {label} do not belong to this company")

    if target.branch_ids:
        from app.models import Branch

        owned_branches = set(
            await db.scalars(
                select(Branch.id).where(
                    Branch.company_id == company_id,
                    Branch.id.in_(target.branch_ids),
                )
            )
        )
        if owned_branches != set(target.branch_ids):
            raise ValueError("One or more branches do not belong to this company")

    if target.excluded_candidate_ids:
        owned_candidates = set(
            await db.scalars(
                select(CompanyCandidate.candidate_id).where(
                    CompanyCandidate.company_id == company_id,
                    CompanyCandidate.candidate_id.in_(target.excluded_candidate_ids),
                )
            )
        )
        if owned_candidates != set(target.excluded_candidate_ids):
            raise ValueError("One or more excluded candidates do not belong to this company")


def audience_query(
    company_id: uuid.UUID,
    vacancy_id: uuid.UUID,
    target: VacancyCampaignTarget,
):
    """Return candidate id, Telegram id and tenant-specific language, once per person."""

    stmt = (
        select(CompanyCandidate.candidate_id, Candidate.telegram_user_id, CompanyCandidate.language)
        .join(Candidate, Candidate.id == CompanyCandidate.candidate_id)
        .where(
            CompanyCandidate.company_id == company_id,
            CompanyCandidate.notifications_enabled.is_(True),
        )
    )

    if target.audience_type == "selected_vacancies":
        stmt = stmt.where(
            exists(
                select(Application.id).where(
                    Application.company_id == company_id,
                    Application.candidate_id == CompanyCandidate.candidate_id,
                    Application.vacancy_id.in_(target.source_vacancy_ids),
                )
            )
        )
    elif target.audience_type == "selected_statuses":
        stmt = stmt.where(
            exists(
                select(Application.id).where(
                    Application.company_id == company_id,
                    Application.candidate_id == CompanyCandidate.candidate_id,
                    Application.status_id.in_(target.source_status_ids),
                )
            )
        )

    if target.branch_ids:
        stmt = stmt.where(
            exists(
                select(Application.id).where(
                    Application.company_id == company_id,
                    Application.candidate_id == CompanyCandidate.candidate_id,
                    Application.branch_id.in_(target.branch_ids),
                )
            )
        )
    if target.languages:
        stmt = stmt.where(CompanyCandidate.language.in_(target.languages))
    if target.excluded_candidate_ids:
        stmt = stmt.where(CompanyCandidate.candidate_id.notin_(target.excluded_candidate_ids))
    if target.exclude_applied:
        stmt = stmt.where(
            ~exists(
                select(Application.id).where(
                    Application.company_id == company_id,
                    Application.candidate_id == CompanyCandidate.candidate_id,
                    Application.vacancy_id == vacancy_id,
                )
            )
        )
    if target.exclude_rejected:
        # Exclude both candidates rejected now and those rejected earlier but later moved
        # to another step. The wording is intentionally "were rejected", not only "are".
        stmt = stmt.where(
            ~exists(
                select(Application.id)
                .join(ApplicationStatus, ApplicationStatus.id == Application.status_id)
                .where(
                    Application.company_id == company_id,
                    Application.candidate_id == CompanyCandidate.candidate_id,
                    Application.vacancy_id == vacancy_id,
                    ApplicationStatus.system_key == "rejected",
                )
            ),
            ~exists(
                select(ApplicationStatusHistory.id)
                .join(
                    Application,
                    Application.id == ApplicationStatusHistory.application_id,
                )
                .join(
                    ApplicationStatus,
                    ApplicationStatus.id == ApplicationStatusHistory.to_status_id,
                )
                .where(
                    Application.company_id == company_id,
                    Application.candidate_id == CompanyCandidate.candidate_id,
                    Application.vacancy_id == vacancy_id,
                    ApplicationStatus.system_key == "rejected",
                )
            ),
        )
    return stmt.order_by(CompanyCandidate.created_at)


def campaign_target_values(target: VacancyCampaignTarget) -> dict:
    return {
        "audience_type": target.audience_type,
        "source_vacancy_ids": _uuid_strings(target.source_vacancy_ids),
        "source_status_ids": _uuid_strings(target.source_status_ids),
        "branch_ids": _uuid_strings(target.branch_ids),
        "languages": list(target.languages),
        "excluded_candidate_ids": _uuid_strings(target.excluded_candidate_ids),
        "exclude_applied": target.exclude_applied,
        "exclude_rejected": target.exclude_rejected,
    }
