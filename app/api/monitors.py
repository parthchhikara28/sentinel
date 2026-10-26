import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.ratelimit import rate_limit
from app.core.redis import redis
from app.core.urls import assert_public_url
from app.db.base import get_session
from app.db.models import CheckResult, Incident, Monitor, User
from app.schemas.monitor import (
    CheckResultOut,
    CheckResultPage,
    IncidentOut,
    MonitorCreate,
    MonitorOut,
    MonitorPage,
    MonitorUpdate,
)

router = APIRouter(prefix="/v1/monitors", tags=["monitors"])


async def _get_owned(monitor_id: int, user: User, session: AsyncSession) -> Monitor:
    monitor = (
        await session.execute(
            select(Monitor).where(Monitor.id == monitor_id, Monitor.user_id == user.id)
        )
    ).scalar_one_or_none()
    if monitor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Monitor not found")
    return monitor


@router.post("", response_model=MonitorOut, status_code=status.HTTP_201_CREATED)
async def create_monitor(
    payload: MonitorCreate,
    user: User = Depends(rate_limit),
    session: AsyncSession = Depends(get_session),
) -> Monitor:
    try:
        await assert_public_url(str(payload.url))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

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
    user: User = Depends(rate_limit),
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
    user: User = Depends(rate_limit),
    session: AsyncSession = Depends(get_session),
) -> Monitor:
    return await _get_owned(monitor_id, user, session)


@router.patch("/{monitor_id}", response_model=MonitorOut)
async def update_monitor(
    monitor_id: int,
    payload: MonitorUpdate,
    user: User = Depends(rate_limit),
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
    user: User = Depends(rate_limit),
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
    user: User = Depends(rate_limit),
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


@router.get("/{monitor_id}/incidents", response_model=list[IncidentOut])
async def list_incidents(
    monitor_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(rate_limit),
    session: AsyncSession = Depends(get_session),
) -> list[Incident]:
    await _get_owned(monitor_id, user, session)
    rows = await session.execute(
        select(Incident)
        .where(Incident.monitor_id == monitor_id)
        .order_by(Incident.started_at.desc())
        .limit(limit)
    )
    return list(rows.scalars())


STATS_SQL = text("""
SELECT
    count(*)                                   AS total_checks,
    count(*) FILTER (WHERE ok)                 AS ok_checks,
    avg(latency_ms) FILTER (WHERE ok)          AS avg_latency_ms,
    percentile_disc(0.95) WITHIN GROUP (ORDER BY latency_ms)
        FILTER (WHERE ok)                      AS p95_latency_ms,
    max(checked_at)                            AS last_checked_at
FROM check_results
WHERE monitor_id = :monitor_id
  AND checked_at > NOW() - (:hours * INTERVAL '1 hour')
""")


@router.get("/{monitor_id}/stats")
async def monitor_stats(
    monitor_id: int,
    hours: int = Query(default=24, ge=1, le=720),
    user: User = Depends(rate_limit),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await _get_owned(monitor_id, user, session)

    cache_key = f"stats:{monitor_id}:{hours}"
    cached = await redis.get(cache_key)
    if cached:
        payload = json.loads(cached)
        payload["cached"] = True
        return payload

    row = (
        (await session.execute(STATS_SQL, {"monitor_id": monitor_id, "hours": hours}))
        .mappings()
        .one()
    )

    total = row["total_checks"] or 0
    payload = {
        "monitor_id": monitor_id,
        "window_hours": hours,
        "total_checks": total,
        "uptime_percent": round(100 * (row["ok_checks"] or 0) / total, 3)
        if total
        else None,
        "avg_latency_ms": round(float(row["avg_latency_ms"]), 1)
        if row["avg_latency_ms"] is not None
        else None,
        "p95_latency_ms": row["p95_latency_ms"],
        "last_checked_at": row["last_checked_at"].isoformat()
        if row["last_checked_at"]
        else None,
        "cached": False,
    }
    await redis.setex(cache_key, settings.stats_cache_ttl_seconds, json.dumps(payload))
    return payload
