"""Application factory and entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.events.router import router as events_router
from app.users.router import router as users_router


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
