import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.ai_report_repository import AIReportRepository
from app.repositories.block_classification_repository import BlockClassificationRepository
from app.repositories.event_repository import EventRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.page_snapshot_repository import PageSnapshotRepository
from app.repositories.site_repository import SiteRepository
from app.services.gsc_service import GSC_NOT_CONNECTED_MESSAGE, GSCService
from app.services.pagespeed_service import PageSpeedService
from app.services.simple_analytics_service import get_simple_site_analytics
from app.services.site_score_service import calculate_site_score
from app.services.site_status_service import get_site_processing_status


PERIOD_OPTIONS = [
    {"value": "24h", "label": "24 часа", "days": 1},
    {"value": "7d", "label": "7 дней", "days": 7},
    {"value": "30d", "label": "30 дней", "days": 30},
]


class ProductDashboardService:
    """Собирает понятную бизнес-панель сайта без технических таблиц в шаблоне."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.site_repository = SiteRepository(session)
        self.event_repository = EventRepository(session)
        self.report_repository = AIReportRepository(session)
        self.snapshot_repository = PageSnapshotRepository(session)
        self.knowledge_repository = KnowledgeRepository(session)
        self.classification_repository = BlockClassificationRepository(session)
        self.gsc_service = GSCService(session)
        self.pagespeed_service = PageSpeedService(session)

    def normalize_period(self, period: str) -> dict[str, Any]:
        for option in PERIOD_OPTIONS:
            if option["value"] == period:
                return option
        return PERIOD_OPTIONS[1]

    async def get_site_dashboard(self, public_site_id: str, period: str = "7d") -> dict[str, Any] | None:
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return None

        period_option = self.normalize_period(period)
        simple_analytics = await get_simple_site_analytics(self.session, public_site_id, days=period_option["days"])
        site_status = await get_site_processing_status(self.session, public_site_id)
        gsc_summary = await self.gsc_service.get_gsc_summary(public_site_id, period_option["value"])
        gsc_top_queries = await self.gsc_service.get_gsc_top_queries(public_site_id, period_option["value"])
        gsc_time_series = await self.gsc_service.get_gsc_time_series(public_site_id, period_option["value"])
        latest_report = await self.report_repository.get_latest_report_by_site(site.id)
        pagespeed = await self.pagespeed_service.get_latest_by_site(public_site_id)

        chart_data = await self._build_chart_data(site.id, period_option, gsc_time_series or [], gsc_connected=bool(gsc_summary and gsc_summary.get("is_connected")))
        technical_counts = await self._build_technical_counts(site.id)
        site_score = await calculate_site_score(self.session, public_site_id, period_option["value"])
        ai_insights = self._extract_ai_insights(latest_report)

        return {
            "site": site,
            "period": period_option["value"],
            "period_label": period_option["label"],
            "period_options": PERIOD_OPTIONS,
            "site_status": site_status,
            "tracker_analytics": simple_analytics,
            "gsc_summary": gsc_summary or {
                "period": period_option["value"],
                "is_connected": False,
                "message": GSC_NOT_CONNECTED_MESSAGE,
                "clicks": 0,
                "impressions": 0,
                "ctr": 0.0,
                "position": 0.0,
            },
            "gsc_top_queries": gsc_top_queries or [],
            "gsc_time_series": gsc_time_series or [],
            "gsc_connected": bool(gsc_summary and gsc_summary.get("is_connected")),
            "pagespeed": pagespeed,
            "chart_data": chart_data,
            "latest_ai_report": latest_report,
            "ai_insights": ai_insights,
            "tracker_code": (
                f'<script src="{settings.APP_BASE_URL}/static/tracker/tracker.js" '
                f'data-site-id="{site.site_id}"></script>'
            ),
            "technical_counts": technical_counts,
            "site_score": site_score,
        }

    async def _build_chart_data(
        self,
        site_id,
        period_option: dict[str, Any],
        gsc_time_series: list[dict[str, Any]],
        gsc_connected: bool = False,
    ) -> dict[str, Any]:
        period_end = datetime.now(timezone.utc)
        days = period_option["days"]
        is_hourly = days <= 1

        if is_hourly:
            period_start = period_end - timedelta(hours=24)
        else:
            period_start = period_end - timedelta(days=days)

        events = await self.event_repository.get_events_by_period(site_id, period_start, period_end)

        if is_hourly:
            labels = self._build_hourly_labels()
            bucket_fn = lambda e: e.created_at.strftime("%H:00") if e.created_at else None
        else:
            labels = self._build_labels(days)
            bucket_fn = lambda e: e.created_at.date().isoformat() if e.created_at else None

        visits_by_bucket = Counter()
        for event in events:
            if event.event_type == "pageview" and event.created_at:
                bucket = bucket_fn(event)
                if bucket:
                    visits_by_bucket[bucket] += 1

        # GSC данные всегда дневные, поэтому для 24h они недоступны.
        gsc_disabled = not gsc_connected or is_hourly
        gsc_by_day = {point["date"]: point for point in gsc_time_series} if gsc_connected and not is_hourly else {}

        if is_hourly:
            gsc_message = "Search Console обновляется по дням, SEO-метрики доступны в периодах 7 дней и 30 дней."
        elif not gsc_connected:
            gsc_message = "Google Search Console пока не подключен или данных нет."
        else:
            gsc_message = ""

        # JS получает уже подготовленные ряды и только рисует линии на canvas.
        return {
            "labels": labels,
            "gsc_available_for_period": gsc_connected and not is_hourly,
            "gsc_message": gsc_message,
            "series": [
                {
                    "key": "visits",
                    "label": "Посещения сайта",
                    "color": "#2563eb",
                    "values": [visits_by_bucket.get(label, 0) for label in labels],
                },
                {
                    "key": "pageviews",
                    "label": "Просмотры страниц",
                    "color": "#0ea5e9",
                    "values": [visits_by_bucket.get(label, 0) for label in labels],
                },
                {
                    "key": "impressions",
                    "label": "SEO показы",
                    "color": "#16a34a",
                    "disabled": gsc_disabled,
                    "values": [gsc_by_day.get(label, {}).get("impressions") for label in labels] if not gsc_disabled else [],
                },
                {
                    "key": "clicks",
                    "label": "SEO клики",
                    "color": "#dc2626",
                    "disabled": gsc_disabled,
                    "values": [gsc_by_day.get(label, {}).get("clicks") for label in labels] if not gsc_disabled else [],
                },
                {
                    "key": "position",
                    "label": "Средняя позиция",
                    "color": "#7c3aed",
                    "disabled": gsc_disabled,
                    "values": [gsc_by_day.get(label, {}).get("position") for label in labels] if not gsc_disabled else [],
                },
                {
                    "key": "ctr",
                    "label": "CTR",
                    "color": "#f59e0b",
                    "disabled": gsc_disabled,
                    "values": [self._format_ctr(gsc_by_day.get(label, {}).get("ctr")) for label in labels] if not gsc_disabled else [],
                },
            ],
        }

    def _build_hourly_labels(self) -> list[str]:
        now = datetime.now(timezone.utc)
        return [
            (now - timedelta(hours=offset)).strftime("%H:00")
            for offset in reversed(range(24))
        ]

    def _build_labels(self, days: int) -> list[str]:
        today = datetime.now(timezone.utc).date()
        return [
            (today - timedelta(days=offset)).isoformat()
            for offset in reversed(range(days))
        ]

    def _format_ctr(self, value: Any) -> float | None:
        if value is None:
            return None
        return round(float(value) * 100, 2)

    @staticmethod
    def _extract_ai_insights(report) -> dict[str, list[str]]:
        """Извлекает seo/traffic/conversion insights из raw_ai_response отчёта."""
        empty = {"seo_insights": [], "traffic_insights": [], "conversion_insights": []}
        if not report:
            return empty

        raw = getattr(report, "raw_ai_response", None)
        if raw is None:
            return empty

        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return empty

        if not isinstance(raw, dict):
            return empty

        def _to_list(value: Any) -> list[str]:
            if isinstance(value, list):
                return [str(item) for item in value if item]
            return []

        return {
            "seo_insights": _to_list(raw.get("seo_insights")),
            "traffic_insights": _to_list(raw.get("traffic_insights")),
            "conversion_insights": _to_list(raw.get("conversion_insights")),
        }

    async def _build_technical_counts(self, site_id) -> dict[str, int]:
        # Счетчики оставляем только в свернутом debug-блоке для разработчика.
        return {
            "events": await self.event_repository.count_events_by_site(site_id),
            "snapshots": await self.snapshot_repository.count_snapshots_by_site(site_id),
            "knowledge_chunks": await self.knowledge_repository.count_chunks_by_site(site_id),
            "classifications": await self.classification_repository.count_classifications_by_site(site_id),
            "reports": await self.report_repository.count_reports_by_site(site_id),
        }
