from unittest.mock import AsyncMock

from sqlalchemy import func, select

from app.db.models import Incident, Monitor, User
from app.worker.alerts import record_result
from app.worker.checker import CheckOutcome

FAIL = CheckOutcome(ok=False, status_code=500, latency_ms=12, error="boom")
PASS = CheckOutcome(ok=True, status_code=200, latency_ms=12, error=None)


async def _make_monitor(session_factory) -> dict:
    async with session_factory() as s:
        user = User(email="w@example.com", api_key_hash="x" * 64)
        s.add(user)
        await s.flush()
        m = Monitor(
            user_id=user.id,
            name="m",
            url="https://example.com",
            failure_threshold=3,
            webhook_url="https://hooks.example.com/x",
        )
        s.add(m)
        await s.commit()
        await s.refresh(m)
        return {
            "id": m.id,
            "url": m.url,
            "timeout_seconds": m.timeout_seconds,
            "expected_status": m.expected_status,
            "failure_threshold": m.failure_threshold,
            "consecutive_failures": 0,
            "webhook_url": m.webhook_url,
        }


async def test_five_failures_create_exactly_one_incident(session_factory, monkeypatch):
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr("app.worker.alerts.deliver_webhook", sender)
    monitor = await _make_monitor(session_factory)

    for _ in range(5):
        await record_result(AsyncMock(), monitor, FAIL)

    async with session_factory() as s:
        count = (
            await s.execute(select(func.count()).select_from(Incident))
        ).scalar_one()

    assert count == 1, "threshold crossing must be idempotent"
    assert sender.await_count == 1, "exactly one 'down' alert"


async def test_no_alert_below_threshold(session_factory, monkeypatch):
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr("app.worker.alerts.deliver_webhook", sender)
    monitor = await _make_monitor(session_factory)

    for _ in range(2):
        await record_result(AsyncMock(), monitor, FAIL)

    assert sender.await_count == 0, "debouncing: 2 failures < threshold of 3"


async def test_recovery_resolves_incident_and_resets_counter(
    session_factory, monkeypatch
):
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr("app.worker.alerts.deliver_webhook", sender)
    monitor = await _make_monitor(session_factory)

    for _ in range(3):
        await record_result(AsyncMock(), monitor, FAIL)
    await record_result(AsyncMock(), monitor, PASS)

    async with session_factory() as s:
        incident = (await s.execute(select(Incident))).scalar_one()
        mon = await s.get(Monitor, monitor["id"])

    assert incident.resolved_at is not None
    assert mon.consecutive_failures == 0
    assert sender.await_count == 2, "one down alert, one recovery alert"
