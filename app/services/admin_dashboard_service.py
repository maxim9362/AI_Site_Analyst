import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_report import AIReport
from app.models.block_classification import BlockClassification
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.page_snapshot import PageSnapshot
from app.repositories.ai_report_repository import AIReportRepository
from app.repositories.block_classification_repository import BlockClassificationRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.event_repository import EventRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.page_snapshot_repository import PageSnapshotRepository
from app.repositories.site_repository import SiteRepository
from app.services.simple_analytics_service import get_simple_site_analytics
from app.services.site_status_service import get_site_processing_status


PERIOD_OPTIONS = [
    {"value": "24h", "label": "24 часа", "days": 1},
    {"value": "7d", "label": "7 дней", "days": 7},
    {"value": "30d", "label": "30 дней", "days": 30},
]


def _normalize_period(period: str) -> dict:
    for option in PERIOD_OPTIONS:
        if option["value"] == period:
            return option
    return PERIOD_OPTIONS[1]


def _build_performance_chart_data(simple_analytics: dict | None) -> dict:
    timeseries = (simple_analytics or {}).get("timeseries") or {}
    return {
        "labels": timeseries.get("labels") or [],
        "site_visits": timeseries.get("site_visits") or [],
        "pageviews": timeseries.get("pageviews") or [],
        "seo_impressions": [],
        "seo_clicks": [],
        "ctr": [],
        "position": [],
    }


class AdminDashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.client_repository = ClientRepository(session)
        self.site_repository = SiteRepository(session)
        self.event_repository = EventRepository(session)
        self.snapshot_repository = PageSnapshotRepository(session)
        self.knowledge_repository = KnowledgeRepository(session)
        self.classification_repository = BlockClassificationRepository(session)
        self.report_repository = AIReportRepository(session)

    async def get_clients_with_stats(self) -> list[dict]:
        clients = await self.client_repository.list_clients()
        result = []
        for client in clients:
            sites_count = await self.client_repository.count_sites_by_client(client.id)
            result.append({
                "client": client,
                "sites_count": sites_count,
            })
        return result

    async def get_client_detail(self, client_id: uuid.UUID) -> dict | None:
        client = await self.client_repository.get_client(client_id)
        if not client:
            return None

        from app.models.site import Site
        from sqlalchemy import select

        result = await self.session.execute(select(Site).where(Site.client_id == client_id))
        sites = list(result.scalars().all())

        return {
            "client": client,
            "sites": sites,
        }

    async def get_site_detail(self, public_site_id: str, period: str = "7d") -> dict | None:
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return None

        period_option = _normalize_period(period)
        event_stats = await self.event_repository.get_site_event_stats(site.id)
        dashboard_counts = await self._get_site_dashboard_counts(site.id)
        recent_events = await self.event_repository.list_recent_events_by_site(site.id, limit=10)
        recent_snapshots = await self.snapshot_repository.list_recent_snapshots_by_site(site.id, limit=5)
        recent_chunks = await self.knowledge_repository.list_recent_chunks_by_site(site.id, limit=5)
        recent_classifications = await self.classification_repository.list_recent_classifications_by_site(site.id, limit=5)
        latest_report = await self.report_repository.get_latest_report_by_site(site.id)
        site_status = await get_site_processing_status(self.session, public_site_id)
        simple_analytics = await get_simple_site_analytics(self.session, public_site_id, days=period_option["days"])

        return {
            "site": site,
            "period": period_option["value"],
            "period_label": period_option["label"],
            "period_options": PERIOD_OPTIONS,
            "site_status": site_status,
            "simple_analytics": simple_analytics,
            "performance_chart_data": _build_performance_chart_data(simple_analytics),
            "event_stats": event_stats,
            "dashboard_counts": dashboard_counts,
            "recent_events": recent_events,
            "recent_snapshots": recent_snapshots,
            "recent_chunks": recent_chunks,
            "recent_knowledge_chunks": recent_chunks,
            "recent_classifications": recent_classifications,
            "latest_report": latest_report,
        }

    async def _get_site_dashboard_counts(self, site_id: uuid.UUID) -> dict:
        # Эти счетчики нужны админке, чтобы быстро показать готовность сайта к AI-анализу.
        snapshots_count = await self._count_model_rows(PageSnapshot, site_id)
        chunks_count = await self._count_model_rows(KnowledgeChunk, site_id)
        classifications_count = await self._count_model_rows(BlockClassification, site_id)
        reports_count = await self._count_model_rows(AIReport, site_id)

        return {
            "snapshots": snapshots_count,
            "knowledge_chunks": chunks_count,
            "classifications": classifications_count,
            "reports": reports_count,
        }

    async def _count_model_rows(self, model, site_id: uuid.UUID) -> int:
        # Универсальный подсчет держит dashboard компактным без отдельных методов в каждом репозитории.
        result = await self.session.execute(select(func.count()).select_from(model).where(model.site_id == site_id))
        return result.scalar_one() or 0
