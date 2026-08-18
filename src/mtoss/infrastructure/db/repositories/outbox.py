from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mtoss.infrastructure.db.models.outbox import OutboxEventRecord


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim(self, limit: int) -> list[dict[str, object]]:
        statement = (
            select(OutboxEventRecord)
            .where(OutboxEventRecord.published_at.is_(None))
            .order_by(OutboxEventRecord.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        records = list((await self.session.scalars(statement)).all())
        return [
            {
                "id": str(record.id),
                "topic": record.topic,
                "message_key": record.message_key,
                "payload": dict(record.payload),
            }
            for record in records
        ]

    async def mark_published(self, event_id: str) -> None:
        record = await self.session.get(OutboxEventRecord, UUID(event_id))
        if record is None:
            raise LookupError(event_id)
        record.published_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
