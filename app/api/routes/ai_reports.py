from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import VALID_REPORT_TYPES
from app.db.database import get_db
from app.repositories.site_repository import SiteRepository
from app.schemas.ai_report import AIReportRead
from app.services.ai_report_service import AIReportService
from app.tasks.report_tasks import generate_ai_report_task

router = APIRouter(tags=["ai-reports"])


@router.post("/sites/{site_id}/reports/generate", response_model=AIReportRead | dict[str, Any])
async def generate_report(
    site_id: str,
    background_tasks: BackgroundTasks,
    report_type: str = "manual",
    days: int = 7,
    sync: bool = False,
    db: AsyncSession = Depends(get_db),
):
    if report_type not in VALID_REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid report_type. Allowed: {', '.join(VALID_REPORT_TYPES)}")

    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="days must be between 1 and 90")

    site_repository = SiteRepository(db)
    site = await site_repository.get_site_by_site_id(site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    if not site.is_active:
        raise HTTPException(status_code=400, detail="Site is inactive")

    if not sync:
        # В обычном режиме HTTP-запрос только ставит тяжелую генерацию отчета в фон.
        background_tasks.add_task(generate_ai_report_task, site_id, report_type, days)
        return {
            "status": "accepted",
            "message": "AI report generation started",
            "site_id": site_id,
            "report_type": report_type,
            "days": days,
        }

    service = AIReportService(db)
    report = await service.generate_site_report(site_id, report_type=report_type, days=days)
    if not report:
        raise HTTPException(status_code=500, detail="AI report was not created")
    return report


@router.get("/sites/{site_id}/reports", response_model=list[AIReportRead])
async def list_reports(site_id: str, limit: int = 10, db: AsyncSession = Depends(get_db)):
    service = AIReportService(db)
    return await service.list_reports_by_site(site_id, limit)


@router.get("/sites/{site_id}/reports/latest", response_model=AIReportRead)
async def get_latest_report(site_id: str, db: AsyncSession = Depends(get_db)):
    service = AIReportService(db)
    report = await service.get_latest_report(site_id)
    if not report:
        raise HTTPException(status_code=404, detail="No reports found")
    return report
