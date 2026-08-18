from collections.abc import AsyncIterator
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from mtoss.application.intent_service import IntentService
from mtoss.infrastructure.db.repositories.orders import OrderRepository


async def require_internal_key(
    request: Request,
    x_internal_key: str = Header(default=""),
) -> None:
    expected = request.app.state.settings.internal_api_key
    if not compare_digest(x_internal_key, expected):
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
