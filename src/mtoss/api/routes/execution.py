from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mtoss.api.dependencies import get_intent_service, get_session, require_internal_key
from mtoss.api.schemas import CreateIntentRequest, CreateIntentResponse, to_command
from mtoss.application.intent_service import IntentService, RiskRejected
from mtoss.infrastructure.db.repositories.orders import OrderRepository

router = APIRouter(
    prefix="/internal/v1/execution-intents",
    tags=["execution"],
    dependencies=[Depends(require_internal_key)],
)


@router.post("", status_code=201, response_model=CreateIntentResponse)
async def create_intent(
    payload: CreateIntentRequest,
    service: Annotated[IntentService, Depends(get_intent_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CreateIntentResponse:
    try:
        result = await service.create(to_command(payload))
    except RiskRejected as exc:
        try:
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "RISK_REJECTED",
                "decision_id": str(exc.decision.decision_id),
            },
        ) from exc
    except (ValidationError, ValueError) as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_INTENT"},
        ) from exc
    except Exception:
        await session.rollback()
        raise

    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return CreateIntentResponse.from_result(result)


@router.get("/{intent_id}")
async def get_intent(
    intent_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    try:
        record = await OrderRepository(session).get(intent_id)
        if record is None:
            await session.rollback()
            raise HTTPException(status_code=404, detail="intent not found")
        response = {"intent_id": str(record.id), "state": record.state.value}
        await session.rollback()
        return response
    except HTTPException:
        raise
    except Exception:
        await session.rollback()
        raise
