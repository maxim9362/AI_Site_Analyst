import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.site import Site
from app.schemas.client import ClientCreate


class ClientRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_client(self, data: ClientCreate) -> Client:
        client = Client(**data.model_dump())
        self.session.add(client)
        await self.session.commit()
        await self.session.refresh(client)
        return client

    async def get_client(self, client_id: uuid.UUID) -> Client | None:
        result = await self.session.execute(select(Client).where(Client.id == client_id))
        return result.scalar_one_or_none()

    async def list_clients(self) -> list[Client]:
        result = await self.session.execute(select(Client))
        return list(result.scalars().all())

    async def count_sites_by_client(self, client_id: uuid.UUID) -> int:
        result = await self.session.execute(select(func.count()).select_from(Site).where(Site.client_id == client_id))
        return result.scalar_one()
