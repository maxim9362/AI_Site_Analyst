from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.repositories.event_repository import EventRepository
from app.repositories.site_repository import SiteRepository


def _normalize_days(days: int) -> int:
    # Период ограничен для MVP, чтобы случайно не загрузить слишком большой объем событий.
    if days < 1:
        return 7
    if days > 90:
        return 90
    return days


def _empty_analytics(days: int, message: str) -> dict[str, Any]:
    # Единая пустая структура нужна API и админке, чтобы шаблон не проверял технические детали.
    return {
        "period_days": days,
        "message": message,
        "visitors": {
            "unique_visitors": 0,
            "unique_sessions": 0,
        },
        "pageviews": {
            "total": 0,
            "top_pages": [],
        },
        "engagement": {
            "scroll_25": 0,
            "scroll_50": 0,
            "scroll_75": 0,
            "scroll_100": 0,
        },
        "clicks": {
            "total": 0,
            "top_clicks": [],
        },
        "goals": {
            "whatsapp": 0,
            "phone": 0,
            "email": 0,
            "forms": 0,
            "cta": 0,
            "total": 0,
        },
        "funnel": {
            "site_visits": 0,
            "viewed_services": 0,
            "viewed_pricing": 0,
            "contact_actions": 0,
            "form_submits": 0,
        },
    }


def _metadata(event: Event) -> dict[str, Any]:
    # Tracker может прислать пустой metadata, поэтому все проверки идут через безопасный dict.
    if isinstance(event.event_metadata, dict):
        return event.event_metadata
    return {}


def _lower_value(value: Any) -> str:
    return str(value or "").strip().lower()


def _click_label(event: Event) -> str:
    meta = _metadata(event)
    text = str(meta.get("text") or "").strip()
    href = _lower_value(meta.get("href"))

    if text:
        return text[:100]
    if "wa.me" in href or "whatsapp" in href:
        return "WhatsApp"
    if href.startswith("tel:"):
        return "Телефон"
    if href.startswith("mailto:"):
        return "Email"
    return "Неизвестный клик"


def _is_whatsapp(event: Event) -> bool:
    meta = _metadata(event)
    href = _lower_value(meta.get("href"))
    text = _lower_value(meta.get("text"))
    return any(marker in href or marker in text for marker in ("wa.me", "whatsapp", "ватсап", "вацап"))


def _is_phone(event: Event) -> bool:
    meta = _metadata(event)
    href = _lower_value(meta.get("href"))
    text = _lower_value(meta.get("text"))
    return href.startswith("tel:") or "позвонить" in text or "телефон" in text


def _is_email(event: Event) -> bool:
    meta = _metadata(event)
    href = _lower_value(meta.get("href"))
    text = _lower_value(meta.get("text"))
    return href.startswith("mailto:") or "email" in text or "почта" in text


def _is_cta(event: Event) -> bool:
    meta = _metadata(event)
    text = _lower_value(meta.get("text"))
    markers = (
        "получить",
        "оставить заявку",
        "заказать",
        "связаться",
        "консультация",
        "написать",
        "отправить",
    )
    return any(marker in text for marker in markers)


def _is_services_page(event: Event) -> bool:
    path = _lower_value(event.path)
    title = _lower_value(event.title)
    return any(marker in path or marker in title for marker in ("service", "uslugi", "услуг"))


def _is_pricing_page(event: Event) -> bool:
    path = _lower_value(event.path)
    title = _lower_value(event.title)
    return any(marker in path or marker in title for marker in ("price", "pricing", "цены", "стоимость"))


def _build_top_pages(pageview_events: list[Event]) -> list[dict[str, Any]]:
    pages: Counter[tuple[str, str]] = Counter()
    for event in pageview_events:
        path = event.path or "/"
        title = event.title or path
        pages[(path, title)] += 1

    return [
        {"path": path, "title": title, "views": count}
        for (path, title), count in pages.most_common(5)
    ]


def _build_scroll_stats(scroll_events: list[Event]) -> dict[str, int]:
    scroll_stats = {
        "scroll_25": 0,
        "scroll_50": 0,
        "scroll_75": 0,
        "scroll_100": 0,
    }
    for event in scroll_events:
        try:
            depth = int(_metadata(event).get("depth") or 0)
        except (TypeError, ValueError):
            depth = 0

        if depth >= 25:
            scroll_stats["scroll_25"] += 1
        if depth >= 50:
            scroll_stats["scroll_50"] += 1
        if depth >= 75:
            scroll_stats["scroll_75"] += 1
        if depth >= 100:
            scroll_stats["scroll_100"] += 1

    return scroll_stats


async def get_simple_site_analytics(
    db: AsyncSession,
    public_site_id: str,
    days: int = 7,
) -> dict[str, Any] | None:
    days = _normalize_days(days)
    site_repository = SiteRepository(db)
    site = await site_repository.get_site_by_site_id(public_site_id)
    if not site:
        return None

    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=days)
    event_repository = EventRepository(db)
    events = await event_repository.get_events_by_period(site.id, period_start, period_end)

    if not events:
        return _empty_analytics(
            days,
            "Пока недостаточно данных. Система собирает аналитику.",
        )

    # Для production тяжелые агрегации лучше перенести в SQL-запросы или materialized summaries.
    pageview_events = [event for event in events if event.event_type == "pageview"]
    click_events = [event for event in events if event.event_type == "click"]
    scroll_events = [event for event in events if event.event_type == "scroll"]
    form_events = [event for event in events if event.event_type == "form_submit"]

    unique_visitors = len({event.visitor_id for event in events if event.visitor_id})
    unique_sessions = len({event.session_id for event in events if event.session_id})
    click_labels = Counter(_click_label(event) for event in click_events)

    whatsapp = sum(1 for event in click_events if _is_whatsapp(event))
    phone = sum(1 for event in click_events if _is_phone(event))
    email = sum(1 for event in click_events if _is_email(event))
    forms = len(form_events)
    cta = sum(1 for event in click_events if _is_cta(event))
    goals_total = whatsapp + phone + email + forms + cta

    return {
        "period_days": days,
        "message": f"Аналитика за последние {days} дней",
        "visitors": {
            "unique_visitors": unique_visitors,
            "unique_sessions": unique_sessions,
        },
        "pageviews": {
            "total": len(pageview_events),
            "top_pages": _build_top_pages(pageview_events),
        },
        "engagement": _build_scroll_stats(scroll_events),
        "clicks": {
            "total": len(click_events),
            "top_clicks": [
                {"label": label, "count": count}
                for label, count in click_labels.most_common(5)
            ],
        },
        "goals": {
            "whatsapp": whatsapp,
            "phone": phone,
            "email": email,
            "forms": forms,
            "cta": cta,
            # В MVP один клик может попасть в несколько целевых категорий, поэтому total является суммой сигналов.
            "total": goals_total,
        },
        "funnel": {
            "site_visits": len(pageview_events),
            "viewed_services": sum(1 for event in pageview_events if _is_services_page(event)),
            "viewed_pricing": sum(1 for event in pageview_events if _is_pricing_page(event)),
            "contact_actions": whatsapp + phone + email + cta,
            "form_submits": forms,
        },
    }
