import json
import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import REPORT_MAX_CONTEXT_LENGTH
from app.repositories.ai_report_repository import AIReportRepository
from app.repositories.block_classification_repository import BlockClassificationRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.page_snapshot_repository import PageSnapshotRepository
from app.repositories.site_repository import SiteRepository
from app.schemas.ai_report import AIReportRead
from app.services.ai_service import ai_service
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)


class AIReportService:
    MAX_CONTEXT_LENGTH = REPORT_MAX_CONTEXT_LENGTH

    def __init__(self, session: AsyncSession):
        self.session = session
        self.report_repository = AIReportRepository(session)
        self.site_repository = SiteRepository(session)
        self.knowledge_repository = KnowledgeRepository(session)
        self.classification_repository = BlockClassificationRepository(session)
        self.snapshot_repository = PageSnapshotRepository(session)
        self.analytics_service = AnalyticsService(session)

    def _build_context(self, analytics: dict, chunks: list, classifications: list, snapshots: list) -> str:
        parts = []

        parts.append("=== АНАЛИТИКА САЙТА ===")
        parts.append(json.dumps(analytics, ensure_ascii=False, default=str)[:3000])

        if chunks:
            parts.append("\n=== ТЕКСТЫ САЙТА (KNOWLEDGE CHUNKS) ===")
            chunks_text = ""
            for chunk in chunks[:20]:
                chunks_text += f"[{chunk.chunk_type}] {chunk.title}: {chunk.content[:200]}\n"
            parts.append(chunks_text[:3000])

        if classifications:
            parts.append("\n=== КЛАССИФИКАЦИЯ БЛОКОВ ===")
            class_text = ""
            for cls in classifications[:15]:
                class_text += f"[{cls.category}] (уверенность: {cls.confidence:.0%}) {cls.reason}\n"
            parts.append(class_text[:2000])

        if snapshots:
            parts.append("\n=== СТРУКТУРА СТРАНИЦ ===")
            snap_text = ""
            for snap in snapshots[:5]:
                snap_text += f"Страница: {snap.path} ({snap.title})\n"
                if snap.headings:
                    for h in snap.headings[:5]:
                        snap_text += f"  - {h.get('tag', 'h1')}: {h.get('text', '')}\n"
            parts.append(snap_text[:2000])

        context = "\n".join(parts)

        if len(context) > self.MAX_CONTEXT_LENGTH:
            context = context[:self.MAX_CONTEXT_LENGTH]

        return context

    async def generate_site_report(self, public_site_id: str, report_type: str = "manual", days: int = 7) -> AIReportRead | None:
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return None

        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=days)

        analytics = await self.analytics_service.get_site_analytics_summary(public_site_id, period_start, period_end)

        chunks = await self.knowledge_repository.list_chunks_by_site(site.id, limit=20)
        classifications = await self.classification_repository.list_classifications_by_site(site.id, limit=15)
        snapshots = await self.snapshot_repository.list_recent_snapshots_by_site(site.id, limit=5)

        context = self._build_context(analytics, chunks, classifications, snapshots)

        logger.info(f"Generating AI report for site {public_site_id} ({report_type}, {days} days)")

        ai_result = await ai_service.generate_report(context)

        report_data = {
            "site_id": site.id,
            "public_site_id": public_site_id,
            "period_start": period_start,
            "period_end": period_end,
            "report_type": report_type,
            "summary": ai_result.get("summary", ""),
            "main_problem": ai_result.get("main_problem", ""),
            "recommendations": ai_result.get("recommendations", []),
            "funnel": ai_result.get("funnel", {}),
            "strengths": ai_result.get("strengths", []),
            "weaknesses": ai_result.get("weaknesses", []),
            "missing_information": ai_result.get("missing_information", []),
            "raw_ai_response": ai_result,
        }

        try:
            report = await self.report_repository.create_report(report_data)
            logger.info(f"AI report created: {report.id}")
            return AIReportRead.model_validate(report)
        except Exception as e:
            logger.error(f"Failed to save AI report: {e}")
            return None

    async def list_reports_by_site(self, public_site_id: str, limit: int = 10) -> list[AIReportRead]:
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return []

        reports = await self.report_repository.list_reports_by_site(site.id, limit)
        return [AIReportRead.model_validate(r) for r in reports]

    async def get_latest_report(self, public_site_id: str) -> AIReportRead | None:
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return None

        report = await self.report_repository.get_latest_report_by_site(site.id)
        if not report:
            return None
        return AIReportRead.model_validate(report)
