import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.event import Event
from app.repositories.pagespeed_repository import PageSpeedRepository
from app.schemas.site import SiteRead, UserSiteCreate
from app.services.gsc_demo_service import create_demo_gsc_data
from app.services.site_service import SiteService

logger = logging.getLogger(__name__)


DEMO_SITE_NAME = "Демо-сайт: нотариальные услуги"
DEMO_DOMAIN = "localhost:8000"
DEMO_GOOGLE_CLIENT_ID = "local-demo-google-client-id"
DEMO_GOOGLE_CLIENT_SECRET = "local-demo-google-client-secret"


def is_demo_site_bootstrap_enabled() -> bool:
    return settings.ENABLE_DEMO_ENDPOINTS and not settings.is_production


async def create_demo_site_for_user(db: AsyncSession, user_id: uuid.UUID) -> SiteRead | None:
    if not is_demo_site_bootstrap_enabled():
        return None

    site_service = SiteService(db)
    site = await site_service.create_site_for_user(
        user_id,
        UserSiteCreate(
            name=DEMO_SITE_NAME,
            domain=DEMO_DOMAIN,
            allowed_domains=["localhost", "127.0.0.1"],
            google_client_id=DEMO_GOOGLE_CLIENT_ID,
            google_client_secret=DEMO_GOOGLE_CLIENT_SECRET,
        ),
    )

    try:
        await seed_demo_site_data(db, site)
    except Exception:
        logger.exception("Failed to seed demo site data for %s", site.site_id)

    return site


async def seed_demo_site_data(db: AsyncSession, site: SiteRead) -> None:
    now = datetime.now(timezone.utc)
    events: list[Event] = []
    pages = [
        ("/", "Главная"),
        ("/services", "Услуги"),
        ("/pricing", "Цены"),
        ("/contact", "Контакты"),
    ]

    for day_offset in range(7):
        day_start = now - timedelta(days=6 - day_offset)
        visitors_count = 5 + day_offset * 2

        for visitor_index in range(visitors_count):
            visitor_id = f"demo-human-{day_offset}-{visitor_index}"
            session_id = f"demo-session-{day_offset}-{visitor_index}"
            first_seen = day_start + timedelta(hours=9 + visitor_index % 9, minutes=visitor_index * 3)

            for page_index, (path, title) in enumerate(pages[: 1 + visitor_index % len(pages)]):
                events.append(_event(site, visitor_id, session_id, "pageview", path, title, first_seen + timedelta(minutes=page_index * 2)))

            depth = 25 * (1 + visitor_index % 4)
            events.append(
                _event(
                    site,
                    visitor_id,
                    session_id,
                    "scroll",
                    "/services",
                    "Услуги",
                    first_seen + timedelta(minutes=8),
                    metadata={"depth": depth},
                )
            )

            if visitor_index % 3 == 0:
                events.append(
                    _event(
                        site,
                        visitor_id,
                        session_id,
                        "click",
                        "/contact",
                        "Контакты",
                        first_seen + timedelta(minutes=11),
                        metadata={"text": "Написать в WhatsApp", "href": "https://wa.me/972501234567", "tag": "a"},
                    )
                )
                events.append(
                    _event(
                        site,
                        visitor_id,
                        session_id,
                        "goal",
                        "/contact",
                        "Контакты",
                        first_seen + timedelta(minutes=12),
                        metadata={"goal_type": "whatsapp"},
                    )
                )

            if visitor_index % 5 == 0:
                events.append(_event(site, visitor_id, session_id, "form_start", "/contact", "Контакты", first_seen + timedelta(minutes=14)))
            if visitor_index % 7 == 0:
                events.append(_event(site, visitor_id, session_id, "form_submit", "/contact", "Контакты", first_seen + timedelta(minutes=17)))

        events.extend(_bot_events(site, day_start, day_offset))

    db.add_all(events)
    await db.commit()
    await _seed_pagespeed(db, site)
    await create_demo_gsc_data(db, site.site_id, days=30)


def _event(
    site: SiteRead,
    visitor_id: str,
    session_id: str,
    event_type: str,
    path: str,
    title: str,
    created_at: datetime,
    *,
    metadata: dict | None = None,
) -> Event:
    return Event(
        site_id=site.id,
        public_site_id=site.site_id,
        visitor_id=visitor_id,
        session_id=session_id,
        event_type=event_type,
        url=f"http://localhost:8000/demo{path if path != '/' else ''}",
        path=path,
        title=title,
        referrer=None,
        event_metadata=metadata or {},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0 Safari/537.36",
        ip_address="127.0.0.1",
        is_bot=False,
        bot_name=None,
        bot_category=None,
        created_at=created_at,
    )


def _bot_events(site: SiteRead, day_start: datetime, day_offset: int) -> list[Event]:
    specs = [
        ("Googlebot", "search_engine", "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"),
        ("AhrefsBot", "seo_tool", "Mozilla/5.0 AhrefsBot/7.0"),
    ]
    events = []
    for index, (name, category, user_agent) in enumerate(specs):
        events.append(
            Event(
                site_id=site.id,
                public_site_id=site.site_id,
                visitor_id=f"demo-bot-{day_offset}-{index}",
                session_id=f"demo-bot-session-{day_offset}-{index}",
                event_type="pageview",
                url="http://localhost:8000/demo",
                path="/" if index == 0 else "/services",
                title="Демо-сайт",
                referrer=None,
                event_metadata={},
                user_agent=user_agent,
                ip_address="127.0.0.1",
                is_bot=True,
                bot_name=name,
                bot_category=category,
                created_at=day_start + timedelta(hours=2 + index),
            )
        )
    return events


async def _seed_pagespeed(db: AsyncSession, site: SiteRead) -> None:
    repository = PageSpeedRepository(db)
    fetched_at = datetime.now(timezone.utc)
    common_metrics = {
        "first-contentful-paint": {"label": "FCP", "score": 0.86, "display_value": "1.4 s", "numeric_value": 1400},
        "largest-contentful-paint": {"label": "LCP", "score": 0.78, "display_value": "2.3 s", "numeric_value": 2300},
        "total-blocking-time": {"label": "TBT", "score": 0.91, "display_value": "80 ms", "numeric_value": 80},
        "cumulative-layout-shift": {"label": "CLS", "score": 0.95, "display_value": "0.04", "numeric_value": 0.04},
        "speed-index": {"label": "Speed Index", "score": 0.84, "display_value": "2.1 s", "numeric_value": 2100},
    }

    for strategy, performance in (("mobile", 82.0), ("desktop", 94.0)):
        await repository.create_result(
            {
                "site_id": site.id,
                "public_site_id": site.site_id,
                "url": "http://localhost:8000/demo",
                "strategy": strategy,
                "fetched_at": fetched_at,
                "performance_score": performance,
                "accessibility_score": 96.0,
                "best_practices_score": 93.0,
                "seo_score": 91.0,
                "metrics": common_metrics,
                "opportunities": [
                    {"id": "render-blocking-resources", "title": "Уменьшить блокирующие ресурсы", "display_value": "0.4 s", "score": 0.72, "overall_savings_ms": 400}
                ],
                "diagnostics": [
                    {"id": "uses-long-cache-ttl", "title": "Настроить кеширование статики", "display_value": "3 ресурса", "score": 0.8}
                ],
                "error": None,
            }
        )
