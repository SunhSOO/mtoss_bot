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

_DUPLICATE_SQLSTATE = "23505"
_IDEMPOTENCY_CONSTRAINT = "uq_order_intent_idempotency"


def _safe_attribute(value: object, name: str) -> object | None:
    try:
        return getattr(value, name, None)
    except Exception:
        return None


def _is_duplicate_intent_integrity_error(error: IntegrityError) -> bool:
    current = _safe_attribute(error, "orig")
    if current is None:
        current = error

    visited: set[int] = set()
    has_duplicate_sqlstate = False
    has_idempotency_constraint = False

    while current is not None:
        identity = id(current)
        if identity in visited:
            break
        visited.add(identity)

        for value in (
            _safe_attribute(current, "sqlstate"),
            _safe_attribute(current, "pgcode"),
        ):
            if value == _DUPLICATE_SQLSTATE:
                has_duplicate_sqlstate = True
        constraint_name = _safe_attribute(current, "constraint_name")
        if constraint_name == _IDEMPOTENCY_CONSTRAINT:
            has_idempotency_constraint = True
        diag = _safe_attribute(current, "diag")
        if diag is not None:
            diag_constraint = _safe_attribute(diag, "constraint_name")
            if diag_constraint == _IDEMPOTENCY_CONSTRAINT:
                has_idempotency_constraint = True

        current = _safe_attribute(current, "__cause__")

    return has_duplicate_sqlstate and has_idempotency_constraint


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
        if _is_duplicate_intent_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "DUPLICATE_INTENT"},
            ) from exc
        raise
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
