from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt as pyjwt
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from src.api.errors import AuthenticationError, ValidationError
from src.api.dependencies import verify_token
from src.config import config
from src.domain.models import User, UserRole
from src.infrastructure.database.models import UserModel
from src.infrastructure.database.repositories import PostgresEventRepository
from src.infrastructure.database.session import db_manager
from src.infrastructure.logging import get_logger
from src.infrastructure.metrics import metrics

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    role: str
    is_active: bool


def _create_access_token(user: User) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": user.user_id,
        "username": user.username,
        "role": user.role.value,
        "iat": now,
        "exp": now + timedelta(minutes=config.auth.access_token_expire_minutes),
        "type": "access",
    }
    return pyjwt.encode(
        payload, config.auth.jwt_secret, algorithm=config.auth.jwt_algorithm
    )


def _create_refresh_token(user: User) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": user.user_id,
        "iat": now,
        "exp": now + timedelta(days=config.auth.refresh_token_expire_days),
        "type": "refresh",
    }
    return pyjwt.encode(
        payload, config.auth.jwt_secret, algorithm=config.auth.jwt_algorithm
    )


def _hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=config.auth.bcrypt_rounds)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"), hashed.encode("utf-8")
    )


async def _get_user_by_username(username: str):
    async with db_manager.session() as session:
        stmt = select(UserModel).where(UserModel.username == username, UserModel.deleted_at.is_(None))
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            return _row_to_user(row)
        return None


async def _get_user_by_email(email: str):
    async with db_manager.session() as session:
        stmt = select(UserModel).where(UserModel.email == email, UserModel.deleted_at.is_(None))
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            return _row_to_user(row)
        return None


def _row_to_user(row: UserModel) -> User:
    return User.from_dict({
        "user_id": row.user_id,
        "username": row.username,
        "email": row.email,
        "hashed_password": row.hashed_password,
        "role": row.role,
        "is_active": row.is_active,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    })


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(request: RegisterRequest) -> TokenResponse:
    existing_user = await _get_user_by_username(request.username)
    if existing_user:
        raise ValidationError("Username already taken")

    existing_email = await _get_user_by_email(request.email)
    if existing_email:
        raise ValidationError("Email already registered")

    user = User(
        username=request.username,
        email=request.email,
        hashed_password=_hash_password(request.password),
        role=UserRole.VIEWER,
    )

    async with db_manager.session() as session:
        model = UserModel(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            hashed_password=user.hashed_password,
            role=user.role.value,
            is_active=user.is_active,
        )
        session.add(model)

    access_token = _create_access_token(user)
    refresh_token = _create_refresh_token(user)

    metrics.increment_counter("users_registered")
    logger.info("User registered: %s", user.username)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=config.auth.access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    user = await _get_user_by_username(request.username)
    if not user:
        raise AuthenticationError("Invalid username or password")

    if not user.is_active:
        raise AuthenticationError("Account is disabled")

    if not _verify_password(request.password, user.hashed_password):
        raise AuthenticationError("Invalid username or password")

    access_token = _create_access_token(user)
    refresh_token = _create_refresh_token(user)

    metrics.increment_counter("user_logins")
    logger.info("User logged in: %s", user.username)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=config.auth.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token_str: str = Header(alias="X-Refresh-Token"),
) -> TokenResponse:
    try:
        payload = pyjwt.decode(
            refresh_token_str,
            config.auth.jwt_secret,
            algorithms=[config.auth.jwt_algorithm],
        )
        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid refresh token")

        user_id = payload.get("sub")
        async with db_manager.session() as session:
            stmt = select(UserModel).where(
                UserModel.user_id == user_id,
                UserModel.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                raise AuthenticationError("User not found")

            user = _row_to_user(row)

        access_token = _create_access_token(user)
        new_refresh_token = _create_refresh_token(user)

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=config.auth.access_token_expire_minutes * 60,
        )

    except pyjwt.ExpiredSignatureError:
        raise AuthenticationError("Refresh token expired")
    except pyjwt.InvalidTokenError:
        raise AuthenticationError("Invalid refresh token")


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    token: dict = Depends(verify_token),
) -> UserResponse:
    async with db_manager.session() as session:
        stmt = select(UserModel).where(
            UserModel.user_id == token["sub"],
            UserModel.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            raise AuthenticationError("User not found")

        return UserResponse(
            user_id=row.user_id,
            username=row.username,
            email=row.email,
            role=row.role,
            is_active=row.is_active,
        )
