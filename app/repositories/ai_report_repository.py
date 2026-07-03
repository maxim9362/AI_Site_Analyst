import uuid

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_report import AIReport


class AIReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_report(self, report_data: dict) -> AIReport:
        report = AIReport(**report_data)
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def get_report(self, report_id: uuid.UUID) -> AIReport | None:
        result = await self.session.execute(select(AIReport).where(AIReport.id == report_id))
        return result.scalar_one_or_none()

    async def list_reports_by_site(self, site_id: uuid.UUID, limit: int = 10, offset: int = 0) -> list[AIReport]:
        result = await self.session.execute(
            select(AIReport).where(AIReport.site_id == site_id).order_by(AIReport.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest_report_by_site(self, site_id: uuid.UUID) -> AIReport | None:
        result = await self.session.execute(
            select(AIReport).where(AIReport.site_id == site_id).order_by(AIReport.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def count_reports_by_site(self, site_id: uuid.UUID) -> int:
        result = await self.session.execute(select(func.count()).select_from(AIReport).where(AIReport.site_id == site_id))
        return result.scalar_one() or 0

    async def get_latest_created_at_by_site(self, site_id: uuid.UUID) -> datetime | None:
        # Для верхнего статуса достаточно даты последнего AI-отчета.
        result = await self.session.execute(select(func.max(AIReport.created_at)).where(AIReport.site_id == site_id))
        return result.scalar_one_or_none()
