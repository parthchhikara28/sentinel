import httpx

from app.db.base import SessionLocal
from app.db.models import CheckResult
from app.worker.checker import CheckOutcome


async def record_result(
    client: httpx.AsyncClient, monitor: dict, outcome: CheckOutcome
) -> None:
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
