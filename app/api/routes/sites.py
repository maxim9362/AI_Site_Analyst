import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.site import SiteCreate, SiteRead
from app.services.site_service import SiteService

router = APIRouter(tags=["sites"])


@router.post("/clients/{client_id}/sites", response_model=SiteRead, status_code=201)
async def create_site(client_id: uuid.UUID, data: SiteCreate, db: AsyncSession = Depends(get_db)):
    service = SiteService(db)
    return await service.create_site(client_id, data)


@router.get("/clients/{client_id}/sites", response_model=list[SiteRead])
async def list_sites(client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = SiteService(db)
    return await service.list_sites_by_client(client_id)


@router.get("/sites/{site_id}", response_model=SiteRead)
async def get_site_by_site_id(site_id: str, db: AsyncSession = Depends(get_db)):
    service = SiteService(db)
    site = await service.get_site_by_site_id(site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site
