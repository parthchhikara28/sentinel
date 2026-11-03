from app.db.models import CheckResult


async def test_list_monitors_includes_latest_status(
    client, user_and_key, session_factory
):
    _, key = user_and_key
    created = await client.post(
        "/v1/monitors",
        headers={"X-API-Key": key},
        json={"name": "example", "url": "https://example.com"},
    )
    monitor_id = created.json()["id"]

    async with session_factory() as s:
        s.add(
            CheckResult(monitor_id=monitor_id, status_code=200, latency_ms=5, ok=True)
        )
        await s.commit()

    r = await client.get("/v1/monitors", headers={"X-API-Key": key})
    item = r.json()["items"][0]
    assert item["latest_status"]["ok"] is True
    assert item["latest_status"]["status_code"] == 200
