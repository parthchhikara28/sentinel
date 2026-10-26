import asyncio
import logging
import random
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.models import CheckResult, Incident, Monitor
from app.worker.checker import CheckOutcome

log = logging.getLogger("alerts")


async def deliver_webhook(
    client: httpx.AsyncClient, url: str, payload: dict, attempts: int = 3
) -> bool:
    for attempt in range(attempts):
        try:
            response = await client.post(url, json=payload, timeout=5.0)
            if response.status_code < 300:
                return True
            if response.status_code < 500:
                # 4xx means our request is wrong; retrying will not help.
                log.warning("webhook rejected %s: %s", url, response.status_code)
                return False
        except httpx.HTTPError as exc:
            log.warning("webhook attempt %s failed: %s", attempt + 1, exc)
        await asyncio.sleep(2**attempt + random.random())
    return False


async def record_result(
    client: httpx.AsyncClient, monitor: dict, outcome: CheckOutcome
) -> None:
    alert: dict | None = None
    webhook_url = monitor.get("webhook_url")

    async with SessionLocal() as session:
        async with session.begin():
            session.add(
                CheckResult(
                    monitor_id=monitor["id"],
                    status_code=outcome.status_code,
                    latency_ms=outcome.latency_ms,
                    ok=outcome.ok,
                    error=outcome.error,
                )
            )

            # Lock the monitor row so two concurrent results cannot both
            # increment the counter from the same starting value.
            row = await session.get(Monitor, monitor["id"], with_for_update=True)
            if row is None:
                return

            open_incident = (
                await session.execute(
                    select(Incident).where(
                        Incident.monitor_id == row.id,
                        Incident.resolved_at.is_(None),
                    )
                )
            ).scalar_one_or_none()

            if outcome.ok:
                row.consecutive_failures = 0
                if open_incident is not None:
                    open_incident.resolved_at = datetime.now(UTC)
                    alert = {
                        "event": "recovered",
                        "monitor_id": row.id,
                        "monitor_name": row.name,
                        "url": row.url,
                        "incident_id": open_incident.id,
                        "downtime_seconds": int(
                            (
                                open_incident.resolved_at - open_incident.started_at
                            ).total_seconds()
                        ),
                    }
            else:
                row.consecutive_failures += 1
                if (
                    row.consecutive_failures >= row.failure_threshold
                    and open_incident is None
                ):
                    incident = Incident(
                        monitor_id=row.id,
                        cause=outcome.error or "check failed",
                        alert_sent=True,
                    )
                    session.add(incident)
                    alert = {
                        "event": "down",
                        "monitor_id": row.id,
                        "monitor_name": row.name,
                        "url": row.url,
                        "cause": outcome.error,
                        "consecutive_failures": row.consecutive_failures,
                    }

    # Send outside the transaction: never hold a database lock across a
    # network call to a third party you do not control.
    if alert and webhook_url:
        await deliver_webhook(client, webhook_url, alert)
