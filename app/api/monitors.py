from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.urls import assert_public_url
from app.db.base import get_session
from app.db.models import CheckResult, Monitor, User
from app.schemas.monitor import (
    CheckResultOut,
    CheckResultPage,
    MonitorCreate,
    MonitorOut,
    MonitorPage,
    MonitorUpdate,
)

router = APIRouter(prefix="/v1/monitors", tags=["monitors"])


async def _get_owned(
    monitor_id: int, user: User, session: AsyncSession
) -> Monitor:
    monitor = (
        await session.execute(
            select(Monitor).where(
                Monitor.id == monitor_id, Monitor.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if monitor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Monitor not found")
    return monitor


@router.post("", response_model=MonitorOut, status_code=status.HTTP_201_CREATED)
async def create_monitor(
    payload: MonitorCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Monitor:
    try:
        await assert_public_url(str(payload.url))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    monitor = Monitor(
        user_id=user.id,
        name=payload.name,
        url=str(payload.url),
        interval_seconds=payload.interval_seconds,
        timeout_seconds=payload.timeout_seconds,
        expected_status=payload.expected_status,
        failure_threshold=payload.failure_threshold,
        webhook_url=str(payload.webhook_url) if payload.webhook_url else None,
    )
    session.add(monitor)
    await session.commit()
    await session.refresh(monitor)
    return monitor


@router.get("", response_model=MonitorPage)
async def list_monitors(
    limit: int = Query(default=50, ge=1, le=100),
    cursor: int | None = Query(default=None, description="last id from previous page"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MonitorPage:
    stmt = select(Monitor).where(Monitor.user_id == user.id)
    if cursor is not None:
        stmt = stmt.where(Monitor.id > cursor)
    stmt = stmt.order_by(Monitor.id).limit(limit + 1)

    rows = list((await session.execute(stmt)).scalars())
    has_more = len(rows) > limit
    rows = rows[:limit]
    return MonitorPage(
        items=[MonitorOut.model_validate(r) for r in rows],
        next_cursor=rows[-1].id if has_more and rows else None,
    )


@router.get("/{monitor_id}", response_model=MonitorOut)
async def get_monitor(
    monitor_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Monitor:
    return await _get_owned(monitor_id, user, session)


@router.patch("/{monitor_id}", response_model=MonitorOut)
async def update_monitor(
    monitor_id: int,
    payload: MonitorUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Monitor:
    monitor = await _get_owned(monitor_id, user, session)
    data = payload.model_dump(exclude_unset=True)
    if "webhook_url" in data and data["webhook_url"] is not None:
        data["webhook_url"] = str(data["webhook_url"])
    for field, value in data.items():
        setattr(monitor, field, value)
    await session.commit()
    await session.refresh(monitor)
    return monitor


@router.delete("/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitor(
    monitor_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    monitor = await _get_owned(monitor_id, user, session)
    monitor.is_active = False
    await session.commit()


@router.get("/{monitor_id}/checks", response_model=CheckResultPage)
async def list_checks(
    monitor_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CheckResultPage:
    await _get_owned(monitor_id, user, session)
    stmt = select(CheckResult).where(CheckResult.monitor_id == monitor_id)
    if cursor is not None:
        stmt = stmt.where(CheckResult.id < cursor)
    stmt = stmt.order_by(CheckResult.id.desc()).limit(limit + 1)

    rows = list((await session.execute(stmt)).scalars())
    has_more = len(rows) > limit
    rows = rows[:limit]
    return CheckResultPage(
        items=[CheckResultOut.model_validate(r) for r in rows],
        next_cursor=rows[-1].id if has_more and rows else None,
    )
