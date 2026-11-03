import asyncio
import random
from datetime import UTC, datetime, timedelta

import asyncpg

from app.config import settings

RAW_URL = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
MONITORS = 5_000
CHECKS_PER_MONITOR = 100
CHECK_COLUMNS = ["monitor_id", "checked_at", "status_code", "latency_ms", "ok", "error"]


async def main() -> None:
    conn = await asyncpg.connect(RAW_URL)
    now = datetime.now(UTC)

    user_id = await conn.fetchval(
        "INSERT INTO users (email, api_key_hash, created_at) "
        "VALUES ($1, $2, now()) RETURNING id",
        f"seed{random.randint(0, 10**9)}@example.com",
        "z" * 64,
    )

    monitor_rows = [
        (
            user_id,
            f"seed monitor {i}",
            f"https://example.com/{i}",
            60,
            10,
            200,
            3,
            None,
            True,
            now,
            0,
            now,
        )
        for i in range(MONITORS)
    ]
    await conn.copy_records_to_table(
        "monitors",
        records=monitor_rows,
        columns=[
            "user_id",
            "name",
            "url",
            "interval_seconds",
            "timeout_seconds",
            "expected_status",
            "failure_threshold",
            "webhook_url",
            "is_active",
            "next_check_at",
            "consecutive_failures",
            "created_at",
        ],
    )
    print(f"inserted {MONITORS} monitors")

    ids = [r["id"] for r in await conn.fetch("SELECT id FROM monitors")]
    batch = []
    for monitor_id in ids:
        for j in range(CHECKS_PER_MONITOR):
            ok = random.random() > 0.02
            batch.append(
                (
                    monitor_id,
                    now - timedelta(minutes=j),
                    200 if ok else 500,
                    random.randint(40, 900),
                    ok,
                    None if ok else "expected 200, got 500",
                )
            )
        if len(batch) >= 50_000:
            await conn.copy_records_to_table(
                "check_results", records=batch, columns=CHECK_COLUMNS
            )
            batch.clear()
            print("...50k check results")
    if batch:
        await conn.copy_records_to_table(
            "check_results", records=batch, columns=CHECK_COLUMNS
        )

    await conn.execute("ANALYZE monitors; ANALYZE check_results;")
    print("done")
    await conn.close()


asyncio.run(main())
