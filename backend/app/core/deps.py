"""FastAPI dependencies — authentication and, critically, tenant resolution.

Tenant isolation rule for the whole codebase: routers never accept a ``company_id`` from
the client as a trusted value. They depend on ``CurrentCompany``, which resolves the
company from the caller's *verified membership*, and then filter every query by
``company_id == company.id``. A row that is fetched by primary key alone (e.g.
``/vacancies/{id}``) must still be re-checked against the current company — the helpers
``get_owned_or_404`` below exist so that check is never forgotten.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_token
from app.models import Company, CompanyMember, User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = decode_token(credentials.credentials, "access")
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token") from None
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_membership(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_company_id: Annotated[str | None, Header(alias="X-Company-Id")] = None,
) -> CompanyMember:
    """Resolve the company the caller is acting on behalf of, and prove membership.

    When ``X-Company-Id`` is omitted we fall back to the caller's only company, which keeps
    the common single-company case ergonomic. With several companies the header is required
    so we never guess which tenant a write belongs to.
    """
    stmt = select(CompanyMember).where(CompanyMember.user_id == user.id)
    if x_company_id:
        try:
            company_id = uuid.UUID(x_company_id)
        except ValueError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "X-Company-Id is not a valid UUID"
            ) from None
        stmt = stmt.where(CompanyMember.company_id == company_id)

    memberships = list((await db.execute(stmt)).scalars().all())
    if not memberships:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You are not a member of this company"
        )
    if len(memberships) > 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "You belong to several companies — send the X-Company-Id header",
        )
    return memberships[0]


CurrentMembership = Annotated[CompanyMember, Depends(get_current_membership)]


async def get_current_company(
    membership: CurrentMembership,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Company:
    company = await db.get(Company, membership.company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    return company


CurrentCompany = Annotated[Company, Depends(get_current_company)]


async def require_owner(membership: CurrentMembership) -> CompanyMember:
    """Bot settings and billing are owner-only (spec §2)."""
    if membership.role != "owner":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the company owner can perform this action"
        )
    return membership


OwnerMembership = Annotated[CompanyMember, Depends(require_owner)]


async def get_owned_or_404(
    db: AsyncSession, model: type, obj_id: uuid.UUID, company_id: uuid.UUID
):
    """Fetch a tenant-owned row by id, 404-ing if it belongs to a different company.

    Returning 404 rather than 403 for a foreign row is deliberate: a 403 would confirm the
    id exists, which leaks the presence of another tenant's records.
    """
    obj = await db.get(model, obj_id)
    if obj is None or obj.company_id != company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__} not found")
    return obj
