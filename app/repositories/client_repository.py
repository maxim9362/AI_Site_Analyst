import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.client import Client
from app.models.site import Site
from app.schemas.client import ClientCreate


class ClientRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_client(self, data: ClientCreate, user_id: uuid.UUID | None = None) -> Client:
        client = Client(user_id=user_id, **data.model_dump())
        self.session.add(client)
        await self.session.commit()
        await self.session.refresh(client)
        return client

    async def get_client(self, client_id: uuid.UUID) -> Client | None:
        result = await self.session.execute(select(Client).where(Client.id == client_id))
        return result.scalar_one_or_none()

    async def get_client_by_email(self, email: str) -> Client | None:
        result = await self.session.execute(select(Client).where(Client.email == email, Client.user_id.is_(None)))
        return result.scalars().first()

    async def list_clients(self) -> list[Client]:
        result = await self.session.execute(select(Client))
        return list(result.scalars().all())

    async def create_user_client(self, user_id: uuid.UUID, data: ClientCreate) -> Client:
        return await self.create_client(data, user_id=user_id)

    async def get_user_client(self, user_id: uuid.UUID, client_id: uuid.UUID) -> Client | None:
        result = await self.session.execute(
            select(Client)
            .options(selectinload(Client.sites))
            .where(Client.id == client_id, Client.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_user_clients(self, user_id: uuid.UUID) -> list[Client]:
        result = await self.session.execute(
            select(Client)
            .options(selectinload(Client.sites))
            .where(Client.user_id == user_id)
            .order_by(Client.created_at.desc())
        )
        return list(result.scalars().all())

    async def count_sites_by_client(self, client_id: uuid.UUID) -> int:
        result = await self.session.execute(select(func.count()).select_from(Site).where(Site.client_id == client_id))
        return result.scalar_one()
