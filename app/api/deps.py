from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_api_key
from app.db.base import get_session
from app.db.models import User


async def get_current_user(
    x_api_key: str = Header(..., description="Your API key"),
    session: AsyncSession = Depends(get_session),
) -> User:
    user = (
        await session.execute(
            select(User).where(User.api_key_hash == hash_api_key(x_api_key))
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return user
