import asyncio
import logging
import signal

import httpx

from app.config import settings
from app.db.base import SessionLocal
from app.worker.alerts import record_result
from app.worker.checker import perform_check
from app.worker.queries import CLAIM_DUE_MONITORS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("worker")

_shutdown = asyncio.Event()


async def claim_batch() -> list[dict]:
    async with SessionLocal() as session:
        async with session.begin():
            rows = await session.execute(
                CLAIM_DUE_MONITORS, {"batch": settings.worker_batch_size}
            )
            return [dict(r) for r in rows.mappings().all()]


async def tick(client: httpx.AsyncClient) -> int:
    monitors = await claim_batch()
    if not monitors:
        return 0

    semaphore = asyncio.Semaphore(settings.worker_concurrency)

    async def guarded(monitor: dict) -> None:
        async with semaphore:
            outcome = await perform_check(client, monitor)
            await record_result(client, monitor, outcome)

    results = await asyncio.gather(
        *(guarded(m) for m in monitors), return_exceptions=True
    )
    for result in results:
        if isinstance(result, Exception):
            log.exception("check failed", exc_info=result)
    return len(monitors)


async def main() -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown.set)

    async with httpx.AsyncClient(
        follow_redirects=True,
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        headers={"User-Agent": "Sentinel/0.1 (uptime monitor)"},
    ) as client:
        log.info("worker started")
        while not _shutdown.is_set():
            try:
                count = await tick(client)
            except Exception:
                log.exception("tick failed")
                count = 0

            delay = (
                0.5
                if count == settings.worker_batch_size
                else settings.worker_idle_sleep_seconds
            )
            try:
                await asyncio.wait_for(_shutdown.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
        log.info("worker stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())
