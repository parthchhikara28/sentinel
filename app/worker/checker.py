import time
from dataclasses import dataclass

import httpx


@dataclass
class CheckOutcome:
    ok: bool
    status_code: int | None
    latency_ms: int
    error: str | None


async def perform_check(client: httpx.AsyncClient, monitor: dict) -> CheckOutcome:
    started = time.perf_counter()
    status_code: int | None = None
    error: str | None = None

    try:
        response = await client.get(monitor["url"], timeout=monitor["timeout_seconds"])
        status_code = response.status_code
        ok = status_code == monitor["expected_status"]
        if not ok:
            error = f"expected {monitor['expected_status']}, got {status_code}"
    except httpx.TimeoutException:
        ok = False
        error = f"timeout after {monitor['timeout_seconds']}s"
    except httpx.HTTPError as exc:
        ok = False
        error = f"{type(exc).__name__}: {exc}"[:500]

    latency_ms = int((time.perf_counter() - started) * 1000)
    return CheckOutcome(
        ok=ok, status_code=status_code, latency_ms=latency_ms, error=error
    )
