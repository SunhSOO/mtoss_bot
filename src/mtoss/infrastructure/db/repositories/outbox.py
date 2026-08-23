from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mtoss.infrastructure.db.models.outbox import OutboxEventRecord


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim(self, limit: int, topic: str | None = None) -> list[dict[str, object]]:
        """`FOR UPDATE SKIP LOCKED`로 집어 온다. 여러 소비자가 같이 돌아도 겹치지 않는다.

        `topic`을 주면 그 토픽만 가져간다. 실행 워커와 알림 워커가 같은 테이블을
        나눠 쓰면서 서로의 이벤트를 삼키지 않게 하려면 필요하다.
        """
        statement = (
            select(OutboxEventRecord)
            .where(OutboxEventRecord.published_at.is_(None))
            .order_by(OutboxEventRecord.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        if topic is not None:
            statement = statement.where(OutboxEventRecord.topic == topic)
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
        try:
            record = await self.session.get(OutboxEventRecord, UUID(event_id))
            if record is None:
                raise LookupError(event_id)
            record.published_at = datetime.now(UTC)
            await self.session.flush()
            await self.session.commit()
        except BaseException:
            await self.session.rollback()
            raise

    async def rollback(self) -> None:
        await self.session.rollback()
