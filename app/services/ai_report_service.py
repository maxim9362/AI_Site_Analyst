import asyncio
import json
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse

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
from app.services.demo_page_service import render_demo_html
from app.services.gsc_service import GSCService
from app.services.pagespeed_service import PageSpeedService
from app.services.public_site_check_service import SiteSignalParser, _fetch_html_sync
from app.services.url_normalization import normalize_public_url

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
        self.gsc_service = GSCService(session)
        self.pagespeed_service = PageSpeedService(session)

    def _build_context(
        self,
        analytics: dict,
        chunks: list,
        classifications: list,
        snapshots: list,
        gsc_data: dict,
        pagespeed_data: dict,
        page_signals: dict | None = None,
    ) -> str:
        # Контекст собирается только из фактов: аналитика, тексты сайта, классификации, снимки и GSC.
        parts = []

        parts.append("=== АНАЛИТИКА САЙТА ===")
        parts.append(json.dumps(analytics, ensure_ascii=False, default=str)[:3000])

        parts.append("\n=== GOOGLE SEARCH CONSOLE ===")
        if gsc_data.get("summary", {}).get("is_connected"):
            parts.append(json.dumps({"google_search_console": gsc_data}, ensure_ascii=False, default=str)[:3000])
            parts.append(
                "Если Search Console данные есть, анализируй SEO-показы, клики, CTR, позиции и запросы вместе с поведением пользователей на сайте."
            )
        else:
            parts.append("Search Console не подключена.")
            parts.append("Если Search Console данных нет, не делай выводы про позиции, показы, CTR или SEO-запросы.")

        # Traffic sources context for AI analysis.
        traffic_sources = analytics.get("traffic_sources", {})
        utm_campaigns = analytics.get("utm_campaigns", {})
        if traffic_sources.get("items") or utm_campaigns.get("items"):
            parts.append("\n=== ИСТОЧНИКИ ТРАФИКА ===")
            parts.append(json.dumps({
                "traffic_sources": traffic_sources,
                "utm_campaigns": utm_campaigns,
            }, ensure_ascii=False, default=str)[:3000])
            parts.append(
                "Если данные по источникам трафика есть, анализируй откуда приходят посетители, "
                "какие каналы работают лучше и есть ли трафик из мессенджеров или соцсетей."
            )

        parts.append("\n=== PAGESPEED INSIGHTS ===")
        if pagespeed_data:
            parts.append(json.dumps({"pagespeed": pagespeed_data}, ensure_ascii=False, default=str)[:3000])
            parts.append(
                "Если данные PageSpeed есть, анализируй скорость, удобство, доступность, техническое качество и SEO-проблемы вместе с поведением пользователей."
            )
        else:
            parts.append("Данные PageSpeed пока не собраны.")

        if page_signals:
            parts.append("\n=== ПРИЗНАКИ ОТКРЫТОЙ СТРАНИЦЫ ===")
            parts.append(json.dumps({"open_page": page_signals}, ensure_ascii=False, default=str)[:3000])
            parts.append(
                "Это признаки открытой страницы: заголовок, подзаголовки, кнопки действия, формы, контакты и фрагменты текста. "
                "Используй их вместе с данными JS-кода, Search Console и PageSpeed. Не придумывай факты, которых нет."
            )

        if chunks:
            parts.append("\n=== ТЕКСТЫ САЙТА ===")
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
                    for heading in snap.headings[:5]:
                        snap_text += f"  - {heading.get('tag', 'h1')}: {heading.get('text', '')}\n"
            parts.append(snap_text[:2000])

        context = "\n".join(parts)

        if len(context) > self.MAX_CONTEXT_LENGTH:
            context = context[:self.MAX_CONTEXT_LENGTH]

        return context

    def _build_page_signals_from_html(self, html: str, status_code: int, final_url: str) -> dict:
        parser = SiteSignalParser()
        parser.feed(html)
        signals = parser.finish()
        signals.status_code = status_code
        signals.final_url = final_url
        return {
            "url": signals.final_url,
            "status_code": signals.status_code,
            "title": signals.title,
            "meta_description": signals.meta_description,
            "h1": signals.h1[:3],
            "h2": signals.h2[:8],
            "cta_texts": signals.cta_texts[:8],
            "forms_count": signals.forms_count,
            "contact_links_count": len(signals.contact_links),
            "sections_count": signals.sections_count,
            "text_length": signals.text_length,
            "text_snippets": signals.text_snippets[:6],
        }

    async def _get_open_page_signals(self, public_site_id: str, domain: str) -> dict | None:
        public_url = normalize_public_url(domain)
        parsed = urlparse(public_url)
        host = (parsed.hostname or "").lower()

        try:
            if host in {"localhost", "127.0.0.1"}:
                html = render_demo_html(public_site_id)
                return self._build_page_signals_from_html(html, 200, f"/demo?site_id={public_site_id}")

            html, status_code, final_url = await asyncio.to_thread(_fetch_html_sync, public_url)
            return self._build_page_signals_from_html(html, status_code, final_url)
        except Exception as exc:
            logger.warning("Could not collect open page signals for %s: %s", public_site_id, str(exc).splitlines()[0][:160])
            return None

    def _gsc_period_from_days(self, days: int) -> str:
        if days <= 1:
            return "24h"
        if days > 7:
            return "30d"
        return "7d"

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

        gsc_period = self._gsc_period_from_days(days)
        gsc_data = {
            "summary": await self.gsc_service.get_gsc_summary(public_site_id, gsc_period),
            "top_queries": await self.gsc_service.get_gsc_top_queries(public_site_id, gsc_period),
            "time_series": await self.gsc_service.get_gsc_time_series(public_site_id, gsc_period),
        }
        pagespeed_data = await self.pagespeed_service.get_ai_context(public_site_id)
        page_signals = await self._get_open_page_signals(public_site_id, site.domain)
        context = self._build_context(analytics, chunks, classifications, snapshots, gsc_data, pagespeed_data, page_signals)

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
