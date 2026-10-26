async def test_create_user_returns_key_once(client):
    r = await client.post("/v1/users", json={"email": "a@example.com"})
    assert r.status_code == 201
    body = r.json()
    assert body["api_key"].startswith("sk_")

    me = await client.get("/v1/users/me", headers={"X-API-Key": body["api_key"]})
    assert me.status_code == 200
    assert "api_key" not in me.json()


async def test_missing_api_key_is_rejected(client):
    r = await client.get("/v1/monitors")
    assert r.status_code in (401, 422)


async def test_wrong_api_key_is_401(client):
    r = await client.get("/v1/monitors", headers={"X-API-Key": "sk_nope"})
    assert r.status_code == 401


async def test_create_monitor(client, user_and_key):
    _, key = user_and_key
    r = await client.post(
        "/v1/monitors",
        headers={"X-API-Key": key},
        json={"name": "example", "url": "https://example.com"},
    )
    assert r.status_code == 201
    assert r.json()["interval_seconds"] == 60


async def test_private_url_rejected(client, user_and_key):
    _, key = user_and_key
    r = await client.post(
        "/v1/monitors",
        headers={"X-API-Key": key},
        json={"name": "bad", "url": "http://127.0.0.1:6379"},
    )
    assert r.status_code == 422


async def test_interval_below_minimum_rejected(client, user_and_key):
    _, key = user_and_key
    r = await client.post(
        "/v1/monitors",
        headers={"X-API-Key": key},
        json={"name": "x", "url": "https://example.com", "interval_seconds": 1},
    )
    assert r.status_code == 422


async def test_cannot_read_another_users_monitor(client):
    a = await client.post("/v1/users", json={"email": "a1@example.com"})
    b = await client.post("/v1/users", json={"email": "b1@example.com"})
    key_a, key_b = a.json()["api_key"], b.json()["api_key"]

    created = await client.post(
        "/v1/monitors",
        headers={"X-API-Key": key_a},
        json={"name": "mine", "url": "https://example.com"},
    )
    monitor_id = created.json()["id"]

    r = await client.get(f"/v1/monitors/{monitor_id}", headers={"X-API-Key": key_b})
    assert r.status_code == 404, "must be 404, not 403 - do not leak existence"
