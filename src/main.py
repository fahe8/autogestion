from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict

from fastapi import FastAPI

from src.core.db import connect_db, disconnect_db
from src.core.security import apply_security_middlewares
from src.core.settings import settings
from src.middlewares.securityHeaders import SecurityHeadersMiddleware
from src.routes.authRoutes import router as auth_router
from src.routes.vacationsRoutes import router as vacations_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await connect_db()
    try:
        yield
    finally:
        await disconnect_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
        lifespan=lifespan,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    apply_security_middlewares(app)

    @app.get("/health", include_in_schema=False)
    async def healthcheck() -> Dict[str, str]:
        return {"status": "ok", "environment": settings.app_env}

    app.include_router(auth_router)
    app.include_router(vacations_router)

    return app


app = create_app()
