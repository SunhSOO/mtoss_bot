from collections.abc import AsyncIterator
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from mtoss.application.intent_service import IntentService
from mtoss.infrastructure.db.repositories.orders import OrderRepository


async def require_internal_key(
    request: Request,
    x_internal_key: str | None = Header(default=None),
) -> None:
    if x_internal_key is None or not x_internal_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid internal key",
        )
    provided = x_internal_key.strip().encode("utf-8")
    expected = request.app.state.settings.internal_api_key
    if not compare_digest(provided, expected.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid internal key",
        )


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


async def get_intent_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IntentService:
    return IntentService(OrderRepository(session))
