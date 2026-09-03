"""Application lifecycle behavior."""

import asyncio

from app import main as main_module
from app.core.config import Settings


async def test_lifespan_starts_and_stops_email_worker(
    monkeypatch,
) -> None:
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def fake_worker(*_: object, **__: object) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(main_module, "run_email_worker", fake_worker)
    application = main_module.create_app(
        Settings(
            jwt_secret="test-secret-that-is-long-enough-for-tests",
            email_outbox_worker_enabled=True,
        )
    )

    async with application.router.lifespan_context(application):
        await asyncio.wait_for(started.wait(), timeout=1)

    assert stopped.is_set()
