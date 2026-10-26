import asyncio

from app.config import settings
from app.db.models import Monitor, User
from app.worker.runner import claim_batch


async def _seed(session_factory, n: int) -> None:
    async with session_factory() as s:
        user = User(email="c@example.com", api_key_hash="y" * 64)
        s.add(user)
        await s.flush()
        for i in range(n):
            s.add(
                Monitor(
                    user_id=user.id,
                    name=f"m{i}",
                    url=f"https://example.com/{i}",
                    interval_seconds=60,
                )
            )
        await s.commit()


async def test_concurrent_claims_are_disjoint(session_factory, monkeypatch):
    monkeypatch.setattr("app.worker.runner.SessionLocal", session_factory)
    # Batch smaller than the number of monitors, so two guards both get work.
    monkeypatch.setattr(settings, "worker_batch_size", 20)
    await _seed(session_factory, 40)

    batch_a, batch_b = await asyncio.gather(claim_batch(), claim_batch())
    ids_a = {m["id"] for m in batch_a}
    ids_b = {m["id"] for m in batch_b}

    assert ids_a and ids_b, "both workers should get work"
    assert not (ids_a & ids_b), "SKIP LOCKED must prevent overlap"


async def test_claim_pushes_next_check_forward(session_factory, monkeypatch):
    monkeypatch.setattr("app.worker.runner.SessionLocal", session_factory)
    await _seed(session_factory, 5)

    first = await claim_batch()
    second = await claim_batch()

    assert len(first) == 5
    assert second == [], "already-claimed monitors are no longer due"
