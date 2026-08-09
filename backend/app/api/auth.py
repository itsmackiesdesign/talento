"""Registration, login, token refresh."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import CurrentUser
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import Company, CompanyMember, User
from app.schemas import (
    CompanyOut,
    LoginRequest,
    MeOut,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])

DB = Annotated[AsyncSession, Depends(get_db)]


def _tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DB) -> TokenPair:
    email = payload.email.lower().strip()
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This email is already registered")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _tokens(user)


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: DB) -> TokenPair:
    user = await db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    # Same message for "no such user" and "wrong password" so the endpoint can't be used
    # to enumerate registered emails.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return _tokens(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: DB) -> TokenPair:
    claims = decode_token(payload.refresh_token, "refresh")
    if claims is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")
    user = await db.get(User, uuid.UUID(claims["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return _tokens(user)


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser, db: DB) -> MeOut:
    """Current user plus the companies they belong to — drives the onboarding redirect."""
    rows = (
        await db.execute(
            select(Company, CompanyMember.role)
            .join(CompanyMember, CompanyMember.company_id == Company.id)
            .where(CompanyMember.user_id == user.id)
            .order_by(Company.created_at)
        )
    ).all()
    return MeOut(
        user=UserOut.model_validate(user),
        companies=[CompanyOut.model_validate(c) for c, _ in rows],
        role=rows[0][1] if rows else None,
    )
