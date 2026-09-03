"""Application factory and entrypoint."""

import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.core.config import Settings, get_settings
from app.core.database import session_factory
from app.core.errors import register_error_handlers
from app.core.security import parse_duration
from app.events.router import router as events_router
from app.mailer.dependencies import create_email_sender
from app.mailer.outbox import run_email_worker
from app.users.router import router as users_router


def _lifespan(
    settings: Settings,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        worker: asyncio.Task[None] | None = None
        if settings.email_outbox_worker_enabled:
            worker = asyncio.create_task(
                run_email_worker(
                    session_factory,
                    create_email_sender(settings),
                    poll_interval=parse_duration(
                        settings.email_outbox_poll_interval
                    ).total_seconds(),
                ),
                name="email-outbox-worker",
            )
        try:
            yield
        finally:
            if worker is not None:
                worker.cancel()
                with suppress(asyncio.CancelledError):
                    await worker

    return lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the ASGI application.

    Takes settings as an argument so tests can construct an app against a
    throwaway database without mutating the environment.
    """
    settings = settings or get_settings()

    app = FastAPI(
        title="Events API",
        description="API for managing events",
        version="1.0",
        docs_url="/api/docs",
        openapi_url="/api/docs-json",
        lifespan=_lifespan(settings),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)

    app.include_router(auth_router)
    app.include_router(events_router)
    app.include_router(users_router)

    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=not settings.is_production,
    )


if __name__ == "__main__":
    main()
