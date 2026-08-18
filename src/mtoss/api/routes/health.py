import asyncio

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request) -> dict[str, str]:
    timeout_seconds = request.app.state.settings.readiness_timeout_seconds
    try:
        async with asyncio.timeout(timeout_seconds):
            async with request.app.state.session_factory() as session:
                await session.execute(text("SELECT 1"))
        async with asyncio.timeout(timeout_seconds):
            if not await request.app.state.redis.ping():
                raise RuntimeError("redis ping failed")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="dependencies unavailable") from exc
    return {"status": "ready"}
