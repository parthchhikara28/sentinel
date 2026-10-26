from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import generate_api_key, hash_api_key
from app.db.base import get_session
from app.db.models import User
from app.schemas.user import UserCreate, UserCreated, UserOut

router = APIRouter(prefix="/v1/users", tags=["users"])


@router.post("", response_model=UserCreated, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserCreated:
    api_key = generate_api_key()
    user = User(email=payload.email, api_key_hash=hash_api_key(api_key))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Email already registered"
        ) from None
    await session.refresh(user)
    return UserCreated(
        id=user.id, email=user.email, created_at=user.created_at, api_key=api_key
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
