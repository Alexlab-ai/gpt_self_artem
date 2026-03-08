from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncGenerator, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import async_session_factory
from db.models import User as UserModel
from repositories.UserRepository import UserRepository


@dataclass
class CurrentUserContext:
    user: UserModel
    session: AsyncSession


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


# Alias for backward compatibility
get_db = get_db_session


def _parse_bearer_token(raw_header: Optional[str]) -> Optional[str]:
    if not raw_header:
        return None
    scheme, _, token = raw_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    token = token.strip()
    return token or None


async def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db_session),
) -> CurrentUserContext:
    """Authenticate user via Bearer token or X-API-Key header."""
    token = _parse_bearer_token(authorization) or (x_api_key.strip() if x_api_key else None)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")

    repo = UserRepository(session)
    user = await repo.get_user_by_api_key(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    await repo.update_last_active(user.id)
    await session.commit()

    return CurrentUserContext(user=user, session=session)


async def get_current_user_by_telegram_id(
    x_telegram_id: str = Header(..., alias="X-Telegram-ID"),
    session: AsyncSession = Depends(get_db_session),
) -> UserModel:
    """Authenticate user by Telegram ID header (for internal/bot use)."""
    stmt = select(UserModel).where(UserModel.telegram_id == x_telegram_id)
    result = await session.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found registered with this Telegram ID.",
        )
    return user
