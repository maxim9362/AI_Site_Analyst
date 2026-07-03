import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.admin_dashboard_service import AdminDashboardService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@router.get("/admin/clients")
async def admin_clients(request: Request, db: AsyncSession = Depends(get_db)):
    service = AdminDashboardService(db)
    clients_data = await service.get_clients_with_stats()
    return templates.TemplateResponse(request, "admin_clients.html", {
        "clients_data": clients_data,
    })


@router.get("/admin/clients/{client_id}")
async def admin_client_detail(request: Request, client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = AdminDashboardService(db)
    data = await service.get_client_detail(client_id)
    if not data:
        return templates.TemplateResponse(request, "index.html", {
            "error": "Client not found",
        })
    return templates.TemplateResponse(request, "admin_client_detail.html", {
        "client": data["client"],
        "sites": data["sites"],
    })


@router.get("/admin/sites/{site_id}")
async def admin_site_detail(request: Request, site_id: str, db: AsyncSession = Depends(get_db)):
    service = AdminDashboardService(db)
    data = await service.get_site_detail(site_id)
    if not data:
        return templates.TemplateResponse(request, "index.html", {
            "error": "Site not found",
        })
    return templates.TemplateResponse(request, "admin_site_detail.html", {
        "site": data["site"],
        "site_status": data["site_status"],
        "simple_analytics": data["simple_analytics"],
        "event_stats": data["event_stats"],
        "dashboard_counts": data["dashboard_counts"],
        "recent_events": data["recent_events"],
        "recent_snapshots": data["recent_snapshots"],
        "recent_chunks": data["recent_chunks"],
        "recent_knowledge_chunks": data["recent_knowledge_chunks"],
        "recent_classifications": data["recent_classifications"],
        "latest_report": data["latest_report"],
    })
