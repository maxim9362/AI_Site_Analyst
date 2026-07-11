import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.site import Site
from app.schemas.site import SiteCreate


class SiteRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_site(
        self,
        client_id: uuid.UUID,
        site_id: str,
        data: SiteCreate,
        user_id: uuid.UUID | None = None,
        google_client_id: str | None = None,
        google_client_secret: str | None = None,
    ) -> Site:
        site = Site(
            client_id=client_id,
            user_id=user_id,
            site_id=site_id,
            google_client_id=google_client_id,
            google_client_secret=google_client_secret,
            **data.model_dump(),
        )
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

    async def get_site_by_site_id_and_user(self, site_id: str, user_id: uuid.UUID) -> Site | None:
        result = await self.session.execute(select(Site).where(Site.site_id == site_id, Site.user_id == user_id))
        return result.scalar_one_or_none()

    async def list_sites_by_client(self, client_id: uuid.UUID) -> list[Site]:
        result = await self.session.execute(select(Site).where(Site.client_id == client_id))
        return list(result.scalars().all())

    async def list_sites_by_user(self, user_id: uuid.UUID) -> list[Site]:
        result = await self.session.execute(select(Site).where(Site.user_id == user_id).order_by(Site.created_at.desc()))
        return list(result.scalars().all())

    async def count_sites_by_user(self, user_id: uuid.UUID) -> int:
        result = await self.session.execute(select(func.count()).select_from(Site).where(Site.user_id == user_id))
        return int(result.scalar_one())
