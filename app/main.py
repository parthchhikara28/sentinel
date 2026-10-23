from fastapi import FastAPI

from app.api import users


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sentinel",
        version="0.1.0",
        description="Uptime monitoring and alerting API",
    )
    app.include_router(users.router)

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
