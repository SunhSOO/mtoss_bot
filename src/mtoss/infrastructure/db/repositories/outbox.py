from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mtoss.infrastructure.db.models.outbox import OutboxEventRecord


class OutboxRepository:
    """Read unpublished outbox records in the caller's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_unpublished(self) -> list[OutboxEventRecord]:
        statement = select(OutboxEventRecord).where(OutboxEventRecord.published_at.is_(None))
        return list((await self.session.scalars(statement)).all())
