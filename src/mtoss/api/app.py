from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from mtoss.api.console.store import ConsoleStore
from mtoss.api.routes.console import router as console_router
from mtoss.api.routes.execution import router as execution_router
from mtoss.api.routes.health import router as health_router
from mtoss.config import Settings
from mtoss.infrastructure.db.session import create_session_factory


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        try:
            if app.state.redis is not None:
                await app.state.redis.aclose()
        finally:
            await app.state.db_engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = (
        Settings()  # type: ignore[call-arg]
        if settings is None
        else Settings.model_validate(settings.model_dump())
    )
    session_factory = create_session_factory(resolved.database_url)
    db_engine = cast(AsyncEngine, session_factory.kw["bind"])

    app = FastAPI(title="mtoss execution core", version="0.1.0", lifespan=_lifespan)
    app.state.settings = resolved
    app.state.session_factory = session_factory
    app.state.db_engine = db_engine
    # 실행 경로는 PostgreSQL 아웃박스만 쓴다. Redis는 선택 사항이고, 없으면 붙이지 않는다.
    app.state.redis = (
        Redis.from_url(resolved.redis_url, decode_responses=True)
        if resolved.redis_url
        else None
    )
    app.include_router(health_router)
    app.include_router(execution_router)
    if resolved.console_stub_enabled:
        app.state.console_store = ConsoleStore()
        app.include_router(console_router)
    return app
