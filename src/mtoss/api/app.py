from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from mtoss.api.routes.execution import router as execution_router
from mtoss.api.routes.health import router as health_router
from mtoss.config import Settings, validate_internal_api_key
from mtoss.infrastructure.db.session import create_session_factory


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        try:
            await app.state.redis.aclose()
        finally:
            await app.state.db_engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()  # type: ignore[call-arg]
    resolved = resolved.model_copy(
        update={"internal_api_key": validate_internal_api_key(resolved.internal_api_key)}
    )
    session_factory = create_session_factory(resolved.database_url)
    db_engine = cast(AsyncEngine, session_factory.kw["bind"])

    app = FastAPI(title="mtoss execution core", version="0.1.0", lifespan=_lifespan)
    app.state.settings = resolved
    app.state.session_factory = session_factory
    app.state.db_engine = db_engine
    app.state.redis = Redis.from_url(resolved.redis_url, decode_responses=True)
    app.include_router(health_router)
    app.include_router(execution_router)
    return app
