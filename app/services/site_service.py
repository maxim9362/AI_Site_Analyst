import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.token_crypto import encode_token
from app.core.config import settings
from app.repositories.client_repository import ClientRepository
from app.repositories.site_repository import SiteRepository
from app.repositories.user_repository import UserRepository
from app.schemas.client import ClientCreate
from app.schemas.site import SiteCreate, SiteRead, UserSiteCreate


class SiteService:
    def __init__(self, session: AsyncSession):
        self.repository = SiteRepository(session)
        self.client_repository = ClientRepository(session)
        self.user_repository = UserRepository(session)

    def _generate_site_id(self) -> str:
        random_part = secrets.token_hex(8)
        return f"site_{random_part}"

    async def create_site(self, client_id: uuid.UUID, data: SiteCreate) -> SiteRead:
        site_id = self._generate_site_id()
        site = await self.repository.create_site(client_id, site_id, data)
        return SiteRead.model_validate(site)

    async def create_site_for_user(self, user_id: uuid.UUID, data: UserSiteCreate) -> SiteRead:
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        client = await self.client_repository.get_client_by_email(user.email)
        if not client:
            client = await self.client_repository.create_client(ClientCreate(name=user.email, email=user.email))

        site_id = self._generate_site_id()
        site_data = SiteCreate(
            name=data.name,
            domain=data.domain,
            allowed_domains=data.allowed_domains,
        )
        site = await self.repository.create_site(
            client.id,
            site_id,
            site_data,
            user_id=user_id,
            google_client_id=data.google_client_id,
            google_client_secret=encode_token(data.google_client_secret),
        )
        return SiteRead.model_validate(site)

    def build_tracker_install_code(self, public_site_id: str) -> str:
        app_base_url = settings.APP_BASE_URL.rstrip("/")
        return (
            f'<script src="{app_base_url}/static/tracker/tracker.js" '
            f'data-site-id="{public_site_id}" async></script>'
        )

    async def get_site_by_site_id(self, site_id: str) -> SiteRead | None:
        site = await self.repository.get_site_by_site_id(site_id)
        if not site:
            return None
        return SiteRead.model_validate(site)

    async def get_user_site_by_site_id(self, user_id: uuid.UUID, site_id: str) -> SiteRead | None:
        site = await self.repository.get_site_by_site_id_and_user(site_id, user_id)
        if not site:
            return None
        return SiteRead.model_validate(site)

    async def list_sites_by_client(self, client_id: uuid.UUID) -> list[SiteRead]:
        sites = await self.repository.list_sites_by_client(client_id)
        return [SiteRead.model_validate(s) for s in sites]

    async def list_sites_by_user(self, user_id: uuid.UUID) -> list[SiteRead]:
        sites = await self.repository.list_sites_by_user(user_id)
        return [SiteRead.model_validate(s) for s in sites]
