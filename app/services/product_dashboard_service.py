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
        gsc_connected = bool(gsc_summary and gsc_summary.get("is_connected"))

        chart_data = await self._build_chart_data(site.id, period_option, gsc_time_series or [], gsc_connected=gsc_connected)
        performance_chart_data = self._build_performance_chart_data(simple_analytics)
        gsc_chart_data = self._build_gsc_chart_data(
            period_option,
            gsc_time_series or [],
            gsc_summary or {},
            gsc_connected=gsc_connected,
        )
        if simple_analytics and simple_analytics.get("realtime_search"):
            simple_analytics["realtime_search"] = self._merge_gsc_into_realtime_search(
                simple_analytics["realtime_search"],
                period_option,
                gsc_summary or {},
                gsc_time_series or [],
                gsc_top_queries or [],
                gsc_connected=gsc_connected,
            )
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
            "traffic_sources": simple_analytics.get("traffic_sources", {"items": [], "total": 0}) if simple_analytics else {"items": [], "total": 0},
            "utm_campaigns": simple_analytics.get("utm_campaigns", {"items": []}) if simple_analytics else {"items": []},
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
            "gsc_connected": gsc_connected,
            "gsc_oauth_configured": settings.google_oauth_configured,
            "gsc_chart_data": gsc_chart_data,
            "pagespeed": pagespeed,
            "chart_data": chart_data,
            "performance_chart_data": performance_chart_data,
            "latest_ai_report": latest_report,
            "ai_insights": ai_insights,
            "tracker_code": (
                f'<script src="{settings.APP_BASE_URL}/static/tracker/tracker.js" '
                f'data-site-id="{site.site_id}"></script>'
            ),
            "technical_counts": technical_counts,
            "site_score": site_score,
        }

    def _build_performance_chart_data(self, simple_analytics: dict[str, Any] | None) -> dict[str, list[Any]]:
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
            if getattr(event, "is_bot", False):
                continue
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

    def _build_gsc_chart_data(
        self,
        period_option: dict[str, Any],
        gsc_time_series: list[dict[str, Any]],
        gsc_summary: dict[str, Any],
        gsc_connected: bool = False,
    ) -> dict[str, Any]:
        days = period_option["days"]
        is_hourly = days <= 1
        labels = self._build_hourly_labels() if is_hourly else self._build_labels(days)
        gsc_by_day = {point["date"]: point for point in gsc_time_series} if gsc_connected and not is_hourly else {}
        latest_point = gsc_time_series[-1] if gsc_time_series else {}
        disabled = not gsc_connected or is_hourly
        if is_hourly:
            message = "Search Console обновляется по дням. Выберите 7 или 30 дней, чтобы увидеть SEO-данные."
        elif not gsc_connected:
            message = "Google Search Console пока не подключен или данных за период нет."
        else:
            message = ""
        note = (
            "Search Console обновляет SEO-данные по дням. В периоде 24 часа SEO-метрики недоступны."
            if is_hourly
            else "Каждая точка на графике соответствует одному дню выбранного периода."
        )

        def values_for(key: str) -> list[float | int | None]:
            if disabled:
                return []
            if is_hourly:
                value = latest_point.get(key)
                if key == "ctr":
                    return [self._format_ctr(value) for _ in labels]
                return [value for _ in labels]
            if key == "ctr":
                return [self._format_ctr(gsc_by_day.get(label, {}).get("ctr")) for label in labels]
            return [gsc_by_day.get(label, {}).get(key) for label in labels]

        return {
            "labels": labels,
            "message": message,
            "note": note,
            "granularity": "hourly" if is_hourly else "daily",
            "summary": [
                {"label": "Показы", "value": int(gsc_summary.get("impressions") or 0), "color": "#16a34a"},
                {"label": "Клики", "value": int(gsc_summary.get("clicks") or 0), "color": "#2563eb"},
                {"label": "CTR", "value": f"{float(gsc_summary.get('ctr') or 0) * 100:.2f}%", "color": "#f59e0b"},
                {"label": "Позиция", "value": f"{float(gsc_summary.get('position') or 0):.1f}", "color": "#7c3aed"},
            ],
            "series": [
                {
                    "key": "impressions",
                    "label": "Показы",
                    "color": "#16a34a",
                    "disabled": disabled,
                    "values": values_for("impressions"),
                },
                {
                    "key": "clicks",
                    "label": "Клики",
                    "color": "#2563eb",
                    "disabled": disabled,
                    "values": values_for("clicks"),
                },
                {
                    "key": "ctr",
                    "label": "CTR",
                    "color": "#f59e0b",
                    "disabled": disabled,
                    "values": values_for("ctr"),
                },
                {
                    "key": "position",
                    "label": "Позиция",
                    "color": "#7c3aed",
                    "disabled": disabled,
                    "values": values_for("position"),
                },
            ],
        }

    def _merge_gsc_into_realtime_search(
        self,
        realtime_search: dict[str, Any],
        period_option: dict[str, Any],
        gsc_summary: dict[str, Any],
        gsc_time_series: list[dict[str, Any]],
        gsc_top_queries: list[dict[str, Any]],
        gsc_connected: bool = False,
    ) -> dict[str, Any]:
        labels = realtime_search.get("labels", [])
        is_hourly = period_option["days"] <= 1
        gsc_by_day = {point["date"]: point for point in gsc_time_series} if gsc_connected and not is_hourly else {}
        latest_point = gsc_time_series[-1] if gsc_time_series else {}
        disabled = not gsc_connected or is_hourly
        if is_hourly:
            message = "Search Console обновляется по дням. Выберите 7 или 30 дней, чтобы увидеть SEO-данные."
        elif not gsc_connected:
            message = "Google Search Console пока не подключен или данных за период нет."
        else:
            message = ""

        def values_for(key: str) -> list[float | int | None]:
            if disabled:
                return []
            if is_hourly:
                value = latest_point.get(key)
                if key == "ctr":
                    return [self._format_ctr(value) for _ in labels]
                return [value for _ in labels]
            if key == "ctr":
                return [self._format_ctr(gsc_by_day.get(label, {}).get("ctr")) for label in labels]
            return [gsc_by_day.get(label, {}).get(key) for label in labels]

        merged = dict(realtime_search)
        merged["source_note"] = (
            "Наши события обновляются сразу. Google Search Console добавляется в этот же график после синхронизации."
        )
        merged["summary"] = list(realtime_search.get("summary", [])) + [
            {
                "label": "Показы Google",
                "value": int(gsc_summary.get("impressions") or 0),
                "color": "#7e22ce",
                "disabled": disabled,
                "info": "Сколько раз сайт был показан пользователям в результатах поиска Google.",
            },
            {
                "label": "Клики Google",
                "value": int(gsc_summary.get("clicks") or 0),
                "color": "#1a73e8",
                "disabled": disabled,
                "info": "Сколько переходов на сайт пришло из результатов поиска Google.",
            },
            {
                "label": "CTR Google",
                "value": f"{float(gsc_summary.get('ctr') or 0) * 100:.2f}%",
                "color": "#f59e0b",
                "disabled": disabled,
                "info": "Доля переходов от показов в Google: клики делятся на показы.",
            },
            {
                "label": "Позиция Google",
                "value": f"{float(gsc_summary.get('position') or 0):.1f}",
                "color": "#7c3aed",
                "disabled": disabled,
                "info": "Среднее место сайта в выдаче Google. Чем меньше число, тем выше сайт.",
            },
        ]
        merged["series"] = list(realtime_search.get("series", [])) + [
            {"key": "google_impressions", "label": "Показы Google", "color": "#7e22ce", "disabled": disabled, "message": message, "values": values_for("impressions")},
            {"key": "google_clicks", "label": "Клики Google", "color": "#1a73e8", "disabled": disabled, "message": message, "values": values_for("clicks")},
            {"key": "google_ctr", "label": "CTR Google", "color": "#f59e0b", "disabled": disabled, "message": message, "values": values_for("ctr")},
            {"key": "google_position", "label": "Позиция Google", "color": "#7c3aed", "disabled": disabled, "message": message, "values": values_for("position")},
        ]

        gsc_query_rows = [
            {
                "primary": query.get("query") or "Без запроса",
                "clicks": int(query.get("clicks") or 0),
                "impressions": int(query.get("impressions") or 0),
                "ctr": f"{float(query.get('ctr') or 0) * 100:.2f}%",
                "position": f"{float(query.get('position') or 0):.1f}",
            }
            for query in gsc_top_queries
        ]
        tabs = []
        for tab in realtime_search.get("tabs", []):
            tab_copy = dict(tab)
            if tab_copy.get("key") == "queries":
                tab_copy["metric_label"] = "Показы"
                tab_copy["rows"] = gsc_query_rows or tab_copy.get("rows", [])
                tab_copy["empty"] = (
                    "Запросы появятся после синхронизации Google Search Console или если поисковик передаст query в referrer."
                )
            tabs.append(tab_copy)
        merged["tabs"] = tabs
        return merged

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
