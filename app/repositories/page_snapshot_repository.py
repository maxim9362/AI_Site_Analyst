import uuid

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.page_snapshot import PageSnapshot


class PageSnapshotRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_snapshot(self, snapshot_data: dict) -> PageSnapshot:
        snapshot = PageSnapshot(**snapshot_data)
        self.session.add(snapshot)
        await self.session.commit()
        await self.session.refresh(snapshot)
        return snapshot

    async def get_snapshot(self, snapshot_id: uuid.UUID) -> PageSnapshot | None:
        # Фоновая обработка получает snapshot заново, чтобы не использовать session из HTTP-запроса.
        result = await self.session.execute(select(PageSnapshot).where(PageSnapshot.id == snapshot_id))
        return result.scalar_one_or_none()

    async def get_latest_snapshot_by_site_and_path(self, site_id: uuid.UUID, path: str) -> PageSnapshot | None:
        result = await self.session.execute(
            select(PageSnapshot).where(PageSnapshot.site_id == site_id, PageSnapshot.path == path).order_by(PageSnapshot.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def list_snapshots_by_site(self, site_id: uuid.UUID, limit: int = 100, offset: int = 0) -> list[PageSnapshot]:
        result = await self.session.execute(
            select(PageSnapshot).where(PageSnapshot.site_id == site_id).order_by(PageSnapshot.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def list_recent_snapshots_by_site(self, site_id: uuid.UUID, limit: int = 5) -> list[PageSnapshot]:
        result = await self.session.execute(
            select(PageSnapshot).where(PageSnapshot.site_id == site_id).order_by(PageSnapshot.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def count_snapshots_by_site(self, site_id: uuid.UUID) -> int:
        result = await self.session.execute(select(func.count()).select_from(PageSnapshot).where(PageSnapshot.site_id == site_id))
        return result.scalar_one() or 0

    async def get_latest_created_at_by_site(self, site_id: uuid.UUID) -> datetime | None:
        # Для статуса достаточно знать, когда был получен последний снимок страницы.
        result = await self.session.execute(select(func.max(PageSnapshot.created_at)).where(PageSnapshot.site_id == site_id))
        return result.scalar_one_or_none()
