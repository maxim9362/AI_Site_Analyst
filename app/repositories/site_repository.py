import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.site import Site
from app.schemas.site import SiteCreate


class SiteRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_site(self, client_id: uuid.UUID, site_id: str, data: SiteCreate) -> Site:
        site = Site(client_id=client_id, site_id=site_id, **data.model_dump())
        self.session.add(site)
        await self.session.commit()
        await self.session.refresh(site)
        return site

    async def get_site(self, site_db_id: uuid.UUID) -> Site | None:
        result = await self.session.execute(select(Site).where(Site.id == site_db_id))
        return result.scalar_one_or_none()

    async def get_site_by_site_id(self, site_id: str) -> Site | None:
        result = await self.session.execute(select(Site).where(Site.site_id == site_id))
        return result.scalar_one_or_none()

    async def list_sites_by_client(self, client_id: uuid.UUID) -> list[Site]:
        result = await self.session.execute(select(Site).where(Site.client_id == client_id))
        return list(result.scalars().all())
