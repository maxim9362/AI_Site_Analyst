import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.client import ClientCreate, ClientRead
from app.services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=ClientRead, status_code=201)
async def create_client(data: ClientCreate, db: AsyncSession = Depends(get_db)):
    service = ClientService(db)
    return await service.create_client(data)


@router.get("", response_model=list[ClientRead])
async def list_clients(db: AsyncSession = Depends(get_db)):
    service = ClientService(db)
    return await service.list_clients()


@router.get("/{client_id}", response_model=ClientRead)
async def get_client(client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = ClientService(db)
    client = await service.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client
