import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.site_repository import SiteRepository
from app.schemas.site import SiteCreate, SiteRead


class SiteService:
    def __init__(self, session: AsyncSession):
        self.repository = SiteRepository(session)

    def _generate_site_id(self) -> str:
        random_part = secrets.token_hex(8)
        return f"site_{random_part}"

    async def create_site(self, client_id: uuid.UUID, data: SiteCreate) -> SiteRead:
        site_id = self._generate_site_id()
        site = await self.repository.create_site(client_id, site_id, data)
        return SiteRead.model_validate(site)

    async def get_site_by_site_id(self, site_id: str) -> SiteRead | None:
        site = await self.repository.get_site_by_site_id(site_id)
        if not site:
            return None
        return SiteRead.model_validate(site)

    async def list_sites_by_client(self, client_id: uuid.UUID) -> list[SiteRead]:
        sites = await self.repository.list_sites_by_client(client_id)
        return [SiteRead.model_validate(s) for s in sites]
