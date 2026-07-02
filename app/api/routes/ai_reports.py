from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.ai_report import AIReportRead
from app.services.ai_report_service import AIReportService

router = APIRouter(tags=["ai-reports"])


@router.post("/sites/{site_id}/reports/generate", response_model=AIReportRead)
async def generate_report(site_id: str, days: int = 7, db: AsyncSession = Depends(get_db)):
    service = AIReportService(db)
    report = await service.generate_site_report(site_id, report_type="manual", days=days)
    if not report:
        raise HTTPException(status_code=404, detail="Site not found")
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
