"""Mini-ATS: application list, detail, status transitions, comments and CSV export."""

import csv
import io
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.deps import CurrentCompany, CurrentUser, get_owned_or_404
from app.core.logging import get_logger
from app.models import (
    Application,
    ApplicationComment,
    ApplicationStatus,
    ApplicationStatusHistory,
    Branch,
    Candidate,
    Vacancy,
)
from app.schemas import (
    ApplicationDetail,
    ApplicationListItem,
    ApplicationPage,
    CommentCreate,
    CommentOut,
    StatusHistoryOut,
    StatusUpdate,
)

router = APIRouter(prefix="/applications", tags=["applications"])
log = get_logger(__name__)

DB = Annotated[AsyncSession, Depends(get_db)]


def _base_query(company_id: uuid.UUID) -> Select:
    return (
        select(Application, Vacancy, Candidate, Branch, ApplicationStatus)
        .join(Vacancy, Vacancy.id == Application.vacancy_id)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(ApplicationStatus, ApplicationStatus.id == Application.status_id)
        .outerjoin(Branch, Branch.id == Vacancy.branch_id)
        .where(Application.company_id == company_id)
    )


def _apply_answer_filters(stmt: Select, answers_filter: str | None) -> Select:
    """``answers_filter`` is a JSON object ``{question_id: value}`` — the panel builds one
    of these once a vacancy is picked, letting HR narrow the board by e.g. "is a student?".
    Each pair is ANDed in as its own ``EXISTS``, since ``answers`` is a JSONB array and a
    single application can only match a question once.

    ``question_id`` in the stored JSONB is a bare ``uuid.hex`` (see
    ``QuestionSnapshot``/``collect_questions`` in app/bot/forms.py) — not the hyphenated form
    the API otherwise uses everywhere — so the incoming id is normalised before comparing.
    """
    if not answers_filter:
        return stmt
    try:
        pairs = json.loads(answers_filter)
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "answers must be valid JSON") from None
    if not isinstance(pairs, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in pairs.items()
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "answers must be a JSON object of {question_id: value}"
        )

    for index, (question_id, value) in enumerate(pairs.items()):
        try:
            question_hex = uuid.UUID(question_id).hex
        except ValueError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"invalid question id: {question_id!r}"
            ) from None
        # `index` only ever comes from enumerate() — safe to interpolate into the alias /
        # bind-param names; the actual values are always bound, never inlined.
        stmt = stmt.where(
            text(
                f"""
                EXISTS (
                    SELECT 1 FROM jsonb_array_elements(applications.answers) AS ans_{index}
                    WHERE ans_{index}->>'question_id' = :qid_{index}
                      AND (
                        ans_{index}->>'answer' = :val_{index}
                        OR (
                          jsonb_typeof(ans_{index}->'answer') = 'array'
                          AND ans_{index}->'answer' ? :val_{index}
                        )
                      )
                )
                """
            ).bindparams(**{f"qid_{index}": question_hex, f"val_{index}": value})
        )
    return stmt


def _apply_filters(
    stmt: Select,
    status_filter: str | None,
    vacancy_id: uuid.UUID | None,
    branch_id: str | None,
    date_from: date | None,
    date_to: date | None,
    search: str | None,
    answers_filter: str | None = None,
) -> Select:
    if status_filter:
        try:
            status_ids = [uuid.UUID(s) for s in status_filter.split(",")]
        except ValueError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "status must be a comma-separated list of ids"
            ) from None
        stmt = stmt.where(Application.status_id.in_(status_ids))
    if vacancy_id:
        stmt = stmt.where(Application.vacancy_id == vacancy_id)
    if branch_id:
        if branch_id.lower() in ("null", "none"):
            stmt = stmt.where(Vacancy.branch_id.is_(None))
        else:
            try:
                stmt = stmt.where(Vacancy.branch_id == uuid.UUID(branch_id))
            except ValueError:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "branch_id must be a UUID or 'null'"
                ) from None
    if date_from:
        start = datetime.combine(date_from, datetime.min.time(), UTC)
        stmt = stmt.where(Application.created_at >= start)
    if date_to:
        end = datetime.combine(date_to, datetime.min.time(), UTC) + timedelta(days=1)
        stmt = stmt.where(Application.created_at < end)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Candidate.first_name.ilike(pattern),
                Candidate.telegram_username.ilike(pattern),
                Candidate.phone.ilike(pattern),
            )
        )
    return _apply_answer_filters(stmt, answers_filter)


def _to_item(
    app: Application,
    vacancy: Vacancy,
    cand: Candidate,
    branch: Branch | None,
    app_status: ApplicationStatus,
):
    return ApplicationListItem(
        id=app.id,
        status_id=app_status.id,
        created_at=app.created_at,
        vacancy_id=vacancy.id,
        vacancy_title=vacancy.title,
        branch_id=branch.id if branch else None,
        branch_name=branch.name if branch else None,
        candidate_name=cand.first_name or "—",
        candidate_username=cand.telegram_username,
        candidate_phone=cand.phone,
    )


@router.get("", response_model=ApplicationPage)
async def list_applications(
    company: CurrentCompany,
    db: DB,
    status_filter: Annotated[
        str | None, Query(alias="status", description="Comma-separated")
    ] = None,
    vacancy_id: uuid.UUID | None = None,
    branch_id: Annotated[str | None, Query()] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: Annotated[str | None, Query(description="Name, @username or phone")] = None,
    answers: Annotated[
        str | None, Query(description='JSON object {question_id: value} — see Settings')
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ApplicationPage:
    stmt = _apply_filters(
        _base_query(company.id),
        status_filter,
        vacancy_id,
        branch_id,
        date_from,
        date_to,
        search,
        answers,
    )

    total = await db.scalar(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ) or 0

    rows = (
        await db.execute(
            stmt.order_by(Application.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    return ApplicationPage(
        items=[_to_item(*row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/export")
async def export_applications(
    company: CurrentCompany,
    db: DB,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    vacancy_id: uuid.UUID | None = None,
    branch_id: Annotated[str | None, Query()] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    answers: Annotated[str | None, Query(description="JSON object {question_id: value}")] = None,
    export_format: Annotated[str, Query(alias="format")] = "csv",
) -> Response:
    """Stream the current filter selection as CSV.

    Generated inline rather than through Celery: the export is a single indexed query and
    the HR expects the file in the same click. If volumes ever outgrow a request timeout,
    move the body of this function into a task and return a job id.
    """
    if export_format != "csv":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only format=csv is supported")

    stmt = _apply_filters(
        _base_query(company.id),
        status_filter,
        vacancy_id,
        branch_id,
        date_from,
        date_to,
        None,
        answers,
    )
    rows = (await db.execute(stmt.order_by(Application.created_at.desc()))).all()

    # Question columns are unioned across the export so a vacancy-specific question still
    # gets its own column instead of being flattened into a blob.
    question_columns: list[str] = []
    for app, *_ in rows:
        for answer in app.answers or []:
            label = answer.get("question_text") or ""
            if label and label not in question_columns:
                question_columns.append(label)

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        ["Дата", "Филиал", "Вакансия", "Имя", "Телефон", "Username", "Статус", *question_columns]
    )

    for app, vacancy, cand, branch, app_status in rows:
        by_label = {}
        for answer in app.answers or []:
            value = answer.get("answer")
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            by_label[answer.get("question_text") or ""] = "" if value is None else str(value)
        writer.writerow(
            [
                app.created_at.strftime("%Y-%m-%d %H:%M"),
                branch.name if branch else "",
                vacancy.title,
                cand.first_name or "",
                cand.phone or "",
                f"@{cand.telegram_username}" if cand.telegram_username else "",
                app_status.label,
                *[by_label.get(col, "") for col in question_columns],
            ]
        )

    filename = f"applications-{datetime.now(UTC):%Y%m%d-%H%M}.csv"
    return Response(
        # BOM so Excel on Windows opens Cyrillic correctly instead of mojibake.
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _load_owned(db: AsyncSession, application_id: uuid.UUID, company_id: uuid.UUID):
    row = (
        await db.execute(
            _base_query(company_id).where(Application.id == application_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return row


@router.get("/{application_id}", response_model=ApplicationDetail)
async def get_application(
    application_id: uuid.UUID, company: CurrentCompany, db: DB
) -> ApplicationDetail:
    # Comments and history are eager-loaded as part of this statement. Note that fetching
    # them via ``db.get(..., options=[...])`` would not work: get() returns straight from
    # the identity map when the row is already loaded and skips the loader options with it,
    # leaving the relationships to lazy-load — which raises MissingGreenlet under asyncio.
    stmt = (
        _base_query(company.id)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.comments).selectinload(ApplicationComment.user),
            selectinload(Application.history).selectinload(ApplicationStatusHistory.user),
        )
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    app, vacancy, cand, branch, app_status = row

    item = _to_item(app, vacancy, cand, branch, app_status)
    return ApplicationDetail(
        **item.model_dump(),
        answers=app.answers or [],
        comments=[
            CommentOut(
                id=c.id,
                text=c.text,
                author_name=c.user.full_name if c.user else "—",
                created_at=c.created_at,
            )
            for c in sorted(app.comments, key=lambda c: c.created_at)
        ],
        history=[
            StatusHistoryOut(
                from_status_label=h.from_status_label,
                to_status_label=h.to_status_label,
                changed_by_name=h.user.full_name if h.user else None,
                created_at=h.created_at,
            )
            for h in sorted(app.history, key=lambda h: h.created_at)
        ],
    )


@router.patch("/{application_id}/status", response_model=ApplicationDetail)
async def update_status(
    application_id: uuid.UUID,
    payload: StatusUpdate,
    company: CurrentCompany,
    user: CurrentUser,
    db: DB,
) -> ApplicationDetail:
    app, _vacancy, _cand, _branch, current_status = await _load_owned(
        db, application_id, company.id
    )

    if app.status_id != payload.status_id:
        target = await get_owned_or_404(db, ApplicationStatus, payload.status_id, company.id)
        app.status_id = target.id
        db.add(
            ApplicationStatusHistory(
                application_id=app.id,
                from_status_id=current_status.id,
                to_status_id=target.id,
                from_status_label=current_status.label,
                to_status_label=target.label,
                changed_by=user.id,
            )
        )
        await db.commit()
        _enqueue_candidate_notification(app.id, current_status.id, target.id)

    return await get_application(application_id, company, db)


def _enqueue_candidate_notification(
    app_id: uuid.UUID, from_status_id: uuid.UUID, to_status_id: uuid.UUID
) -> None:
    from app.workers.tasks import notify_candidate_status

    try:
        notify_candidate_status.delay(str(app_id), str(from_status_id), str(to_status_id))
    except Exception as exc:  # noqa: BLE001 — a broker outage must not fail the status change
        log.warning("candidate_notify_enqueue_failed", error=str(exc))


@router.post(
    "/{application_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED
)
async def add_comment(
    application_id: uuid.UUID,
    payload: CommentCreate,
    company: CurrentCompany,
    user: CurrentUser,
    db: DB,
) -> CommentOut:
    await _load_owned(db, application_id, company.id)
    comment = ApplicationComment(
        application_id=application_id, user_id=user.id, text=payload.text.strip()
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return CommentOut(
        id=comment.id,
        text=comment.text,
        author_name=user.full_name,
        created_at=comment.created_at,
    )


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: uuid.UUID, company: CurrentCompany, db: DB
) -> None:
    """Hard delete — used to honour a candidate's personal-data erasure request (spec §4)."""
    app, *_ = await _load_owned(db, application_id, company.id)
    full = await db.get(Application, app.id)
    await db.delete(full)
    await db.commit()
    log.info("application_deleted", application_id=str(application_id), company_id=str(company.id))


# Vacancy/branch names are needed by the panel's filter dropdowns; exposing them here keeps
# the applications page to a single request on first paint.
@router.get("/meta/filters")
async def filter_options(company: CurrentCompany, db: DB) -> dict:
    vacancies = (
        await db.execute(
            select(Vacancy.id, Vacancy.title)
            .where(Vacancy.company_id == company.id)
            .order_by(Vacancy.sort_order)
        )
    ).all()
    branches = (
        await db.execute(
            select(Branch.id, Branch.name)
            .where(Branch.company_id == company.id)
            .order_by(Branch.sort_order)
        )
    ).all()
    return {
        "vacancies": [{"id": str(i), "title": tt} for i, tt in vacancies],
        "branches": [{"id": str(i), "name": n} for i, n in branches],
    }
