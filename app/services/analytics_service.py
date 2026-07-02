from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.event_repository import EventRepository
from app.repositories.site_repository import SiteRepository


class AnalyticsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.event_repository = EventRepository(session)
        self.site_repository = SiteRepository(session)

    async def get_site_analytics_summary(self, public_site_id: str, period_start: datetime, period_end: datetime) -> dict:
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return {"error": "Site not found"}

        event_stats = await self.event_repository.get_event_stats_by_period(site.id, period_start, period_end)
        click_targets = await self.event_repository.get_click_targets_by_period(site.id, period_start, period_end)
        scroll_depth = await self.event_repository.get_scroll_depth_by_period(site.id, period_start, period_end)

        pages = {}
        events = await self.event_repository.get_events_by_period(site.id, period_start, period_end)
        for event in events:
            path = event.path
            if path not in pages:
                pages[path] = {"path": path, "pageviews": 0, "clicks": 0}
            if event.event_type == "pageview":
                pages[path]["pageviews"] += 1
            elif event.event_type == "click":
                pages[path]["clicks"] += 1

        page_list = sorted(pages.values(), key=lambda x: x["pageviews"], reverse=True)[:20]

        funnel = self._calculate_funnel(events)

        return {
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
            },
            "events": event_stats,
            "users": {
                "unique_visitors": event_stats.get("unique_visitors", 0),
                "unique_sessions": event_stats.get("unique_sessions", 0),
            },
            "pages": page_list,
            "click_targets": click_targets[:30],
            "scroll_depth": scroll_depth,
            "funnel": funnel,
        }

    def _calculate_funnel(self, events: list) -> dict:
        funnel = {
            "pageviews": 0,
            "viewed_services": 0,
            "viewed_pricing": 0,
            "clicked_cta": 0,
            "clicked_whatsapp": 0,
            "clicked_phone": 0,
            "submitted_form": 0,
        }

        service_markers = ("service", "services", "uslug", "uslugi", "услуг")
        pricing_markers = ("price", "pricing", "cost", "czen", "цен", "стоим")
        cta_markers = ("cta", "заявк", "консультац", "заказ", "оставить", "отправить", "получить")

        for event in events:
            metadata = event.event_metadata or {}

            if event.event_type == "pageview":
                funnel["pageviews"] += 1
                path_lower = (event.path or "").lower()
                if any(marker in path_lower for marker in service_markers):
                    funnel["viewed_services"] += 1
                if any(marker in path_lower for marker in pricing_markers):
                    funnel["viewed_pricing"] += 1
            elif event.event_type == "block_view":
                # Просмотры блоков дают более точную воронку, чем URL страницы.
                category = metadata.get("category", "")
                if category == "services":
                    funnel["viewed_services"] += 1
                if category == "pricing":
                    funnel["viewed_pricing"] += 1
            elif event.event_type == "click":
                href = metadata.get("href", "").lower()
                text = metadata.get("text", "").lower()

                if any(marker in text for marker in cta_markers):
                    funnel["clicked_cta"] += 1
                if "wa.me" in href or "whatsapp" in href:
                    funnel["clicked_whatsapp"] += 1
                if "tel:" in href:
                    funnel["clicked_phone"] += 1
            elif event.event_type == "form_submit":
                funnel["submitted_form"] += 1

        return funnel
