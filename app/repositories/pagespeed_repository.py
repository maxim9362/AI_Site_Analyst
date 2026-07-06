import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pagespeed_result import PageSpeedResult


class PageSpeedRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_result(self, data: dict) -> PageSpeedResult:
        result = PageSpeedResult(**data)
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def get_latest_by_site_and_strategy(self, site_id: uuid.UUID, strategy: str) -> PageSpeedResult | None:
        result = await self.session.execute(
            select(PageSpeedResult)
            .where(PageSpeedResult.site_id == site_id, PageSpeedResult.strategy == strategy)
            .order_by(PageSpeedResult.fetched_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_latest_by_site(self, site_id: uuid.UUID) -> dict[str, PageSpeedResult]:
        latest: dict[str, PageSpeedResult] = {}
        for strategy in ("mobile", "desktop"):
            result = await self.get_latest_by_site_and_strategy(site_id, strategy)
            if result:
                latest[strategy] = result
        return latest
