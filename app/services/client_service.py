import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.client_repository import ClientRepository
from app.schemas.client import ClientCreate, ClientRead


class ClientService:
    def __init__(self, session: AsyncSession):
        self.repository = ClientRepository(session)

    async def create_client(self, data: ClientCreate) -> ClientRead:
        client = await self.repository.create_client(data)
        return ClientRead.model_validate(client)

    async def get_client(self, client_id: uuid.UUID) -> ClientRead | None:
        client = await self.repository.get_client(client_id)
        if not client:
            return None
        return ClientRead.model_validate(client)

    async def list_clients(self) -> list[ClientRead]:
        clients = await self.repository.list_clients()
        return [ClientRead.model_validate(c) for c in clients]
