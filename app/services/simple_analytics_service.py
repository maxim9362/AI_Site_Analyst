from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.repositories.event_repository import EventRepository
from app.repositories.site_repository import SiteRepository


TRAFFIC_CHANNEL_LABELS = {
    "organic_search": "Organic Search",
    "social": "Social",
    "messenger": "Messenger",
    "direct": "Direct",
    "referral": "Referral",
}


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def _detect_source_from_referrer(referrer: str | None) -> tuple[str, str] | None:
    """Fallback: определяем источник по URL referrer (для событий без traffic_source metadata)."""
    if not referrer:
        return None
    try:
        host = urlparse(referrer).netloc.lower()
    except Exception:
        return None
    if not host:
        return None
    if "google." in host:
        return "google", "organic_search"
    if _host_matches(host, "facebook.com") or _host_matches(host, "fb.com"):
        return "facebook", "social"
    if _host_matches(host, "instagram.com"):
        return "instagram", "social"
    if "whatsapp" in host or "wa.me" in host:
        return "whatsapp", "messenger"
    if "telegram" in host or _host_matches(host, "t.me"):
        return "telegram", "messenger"
    return host, "referral"


def _detect_source_from_url(url: str | None) -> tuple[str, str] | None:
    """Fallback: определяем источник по UTM-параметрам в URL (для событий без metadata)."""
    if not url:
        return None
    try:
        params = parse_qs(urlparse(url).query)
    except Exception:
        return None
    utm_source = (params.get("utm_source", [""])[0] or "").strip().lower()
    utm_medium = (params.get("utm_medium", [""])[0] or "").strip().lower()
    if not utm_source:
        return None
    source = utm_source
    channel = utm_medium if utm_medium else "unknown"
    # Normalize known channels.
    if source in ("facebook", "fb"):
        source, channel = "facebook", "social"
    elif source in ("instagram", "ig"):
        source, channel = "instagram", "social"
    elif source in ("whatsapp", "wa"):
        source, channel = "whatsapp", "messenger"
    elif source in ("telegram", "tg"):
        source, channel = "telegram", "messenger"
    elif source == "google":
        channel = "organic_search"
    return source, channel


def _resolve_traffic_source(event: Event) -> tuple[str, str]:
    """Определяет source и channel для pageview-события.

    Приоритет: metadata.traffic_source > metadata via event.referrer/url > event.referrer > event.url > direct.
    """
    meta = _metadata(event)

    # 1. Новый tracker прислал traffic_source в metadata.
    source = (meta.get("traffic_source") or "").strip().lower()
    channel = (meta.get("traffic_channel") or "").strip().lower()
    if source:
        return source, channel or "unknown"

    # 2. Fallback: UTM из metadata.
    utm_source = (meta.get("utm_source") or "").strip().lower()
    utm_medium = (meta.get("utm_medium") or "").strip().lower()
    if utm_source:
        return utm_source, utm_medium or "unknown"

    # 3. Fallback: UTM из URL события (старый tracker).
    from_url = _detect_source_from_url(event.url)
    if from_url:
        return from_url

    # 4. Fallback: referrer из события.
    from_ref = _detect_source_from_referrer(event.referrer)
    if from_ref:
        return from_ref

    # 5. Direct.
    return "direct", "direct"


def _build_traffic_sources(pageview_events: list[Event]) -> dict[str, Any]:
    source_counter: Counter[tuple[str, str]] = Counter()
    for event in pageview_events:
        source, channel = _resolve_traffic_source(event)
        source_counter[(source, channel)] += 1

    total = sum(source_counter.values())
    items = []
    for (source, channel), count in source_counter.most_common(10):
        items.append({
            "source": source,
            "channel": TRAFFIC_CHANNEL_LABELS.get(channel, channel),
            "channel_key": channel,
            "visits": count,
            "percent": round(count / total * 100, 1) if total > 0 else 0.0,
        })

    return {"items": items, "total": total}


def _build_utm_campaigns(pageview_events: list[Event]) -> dict[str, Any]:
    campaign_counter: Counter[tuple[str, str, str]] = Counter()
    for event in pageview_events:
        meta = _metadata(event)
        utm_source = meta.get("utm_source")
        utm_medium = meta.get("utm_medium")
        utm_campaign = meta.get("utm_campaign")
        # Fallback: извлекаем UTM из URL события, если в metadata нет.
        if not utm_source and not utm_medium and not utm_campaign and event.url:
            try:
                params = parse_qs(urlparse(event.url).query)
                utm_source = params.get("utm_source", [""])[0] or None
                utm_medium = params.get("utm_medium", [""])[0] or None
                utm_campaign = params.get("utm_campaign", [""])[0] or None
            except Exception:
                pass
        if not utm_source and not utm_medium and not utm_campaign:
            continue
        key = (
            (utm_source or "").strip().lower(),
            (utm_medium or "").strip().lower(),
            (utm_campaign or "").strip().lower(),
        )
        campaign_counter[key] += 1

    items = []
    for (source, medium, campaign), count in campaign_counter.most_common(10):
        items.append({
            "source": source,
            "medium": medium,
            "campaign": campaign,
            "visits": count,
        })

    return {"items": items}


def _build_timeseries(
    events: list[Event],
    days: int,
) -> dict[str, Any]:
    """Строит time series для графика: labels + site_visits + pageviews."""
    period_end = datetime.now(timezone.utc)

    if days <= 1:
        # 24h — labels по часам (последние 24 часа UTC).
        period_start = period_end - timedelta(hours=24)
        labels = [
            (period_end - timedelta(hours=offset)).strftime("%H:00")
            for offset in reversed(range(24))
        ]
        bucket_fn = lambda e: e.created_at.strftime("%H:00") if e.created_at else None
    else:
        # 7d / 30d — labels по дням.
        period_start = period_end - timedelta(days=days)
        labels = [
            (period_end - timedelta(days=offset)).date().isoformat()
            for offset in reversed(range(days))
        ]
        bucket_fn = lambda e: e.created_at.date().isoformat() if e.created_at else None

    pageview_events = [e for e in events if e.event_type == "pageview"]

    visits_by_bucket = Counter()
    for event in pageview_events:
        bucket = bucket_fn(event)
        if bucket:
            visits_by_bucket[bucket] += 1

    # В MVP pageview = site visit (один pageview = один визит на страницу).
    return {
        "labels": labels,
        "site_visits": [visits_by_bucket.get(label, 0) for label in labels],
        "pageviews": [visits_by_bucket.get(label, 0) for label in labels],
    }


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
            "cta": 0,
            "form_starts": 0,
            "form_submits": 0,
            "total": 0,
        },
        "funnel": {
            "site_visits": 0,
            "viewed_services": 0,
            "viewed_pricing": 0,
            "contact_actions": 0,
            "form_starts": 0,
            "form_submits": 0,
        },
        "timeseries": {
            "labels": [],
            "site_visits": [],
            "pageviews": [],
        },
        "bots": {
            "total_events": 0,
            "unique_bots": 0,
            "unique_sessions": 0,
            "known_bots": [],
            "top_user_agents": [],
        },
        "realtime_search": _build_realtime_search_analytics([], [], days),
        "traffic_sources": {"items": [], "total": 0},
        "utm_campaigns": {"items": []},
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


def _period_buckets(days: int) -> tuple[list[str], Any]:
    period_end = datetime.now(timezone.utc)
    if days <= 1:
        labels = [
            (period_end - timedelta(hours=offset)).strftime("%H:00")
            for offset in reversed(range(24))
        ]
        return labels, lambda event: event.created_at.strftime("%H:00") if event.created_at else None

    labels = [
        (period_end - timedelta(days=offset)).date().isoformat()
        for offset in reversed(range(days))
    ]
    return labels, lambda event: event.created_at.date().isoformat() if event.created_at else None


def _extract_search_query(referrer: str | None) -> str | None:
    if not referrer:
        return None
    parsed = urlparse(referrer)
    host = parsed.netloc.lower()
    if not any(search_host in host for search_host in ("google.", "bing.", "yandex.", "duckduckgo.")):
        return None
    params = parse_qs(parsed.query)
    for key in ("q", "query", "text", "p"):
        value = params.get(key, [""])[0].strip()
        if value:
            return value[:120]
    return None


def _device_label(user_agent: str | None) -> str:
    value = (user_agent or "").lower()
    if any(marker in value for marker in ("mobile", "iphone", "android")):
        return "Mobile"
    if any(marker in value for marker in ("ipad", "tablet")):
        return "Tablet"
    if value:
        return "Desktop"
    return "Unknown"


def _source_label(event: Event) -> str:
    referrer = (event.referrer or "").strip()
    if not referrer:
        return "Прямой заход"
    host = urlparse(referrer).netloc.lower()
    if any(search_host in host for search_host in ("google.", "bing.", "yandex.", "duckduckgo.")):
        return "Поиск"
    if any(social in host for social in ("facebook.", "instagram.", "t.co", "twitter.", "linkedin.", "vk.")):
        return "Соцсети"
    return host or "Реферал"


def _count_rows(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"primary": primary, "clicks": 0, "impressions": count}
        for primary, count in counter.most_common(8)
    ]


def _empty_realtime_search_analytics() -> dict[str, Any]:
    return {
        "updated_label": "обновляется в реальном времени",
        "granularity": "daily",
        "labels": [],
        "summary": [],
        "series": [],
        "tabs": [],
    }


def _build_realtime_search_analytics(
    human_events: list[Event],
    bot_events: list[Event],
    days: int,
) -> dict[str, Any]:
    labels, bucket_fn = _period_buckets(days)
    pageview_events = [event for event in human_events if event.event_type == "pageview"]
    click_events = [event for event in human_events if event.event_type == "click"]
    goal_events = [
        event for event in human_events
        if event.event_type in ("goal", "form_start", "form_submit")
    ]

    visitors_by_bucket: dict[str, set[str]] = {label: set() for label in labels}
    pageviews_by_bucket = Counter()
    clicks_by_bucket = Counter()
    goals_by_bucket = Counter()
    bots_by_bucket = Counter()

    for event in pageview_events:
        bucket = bucket_fn(event)
        if not bucket:
            continue
        pageviews_by_bucket[bucket] += 1
        if event.visitor_id:
            visitors_by_bucket.setdefault(bucket, set()).add(event.visitor_id)

    for event in click_events:
        bucket = bucket_fn(event)
        if bucket:
            clicks_by_bucket[bucket] += 1

    for event in goal_events:
        bucket = bucket_fn(event)
        if bucket:
            goals_by_bucket[bucket] += 1

    for event in bot_events:
        bucket = bucket_fn(event)
        if bucket:
            bots_by_bucket[bucket] += 1

    query_counter = Counter(
        query for query in (_extract_search_query(event.referrer) for event in pageview_events) if query
    )
    pages = Counter((event.path or "/") for event in pageview_events)
    countries = Counter({"Unknown": len(pageview_events)}) if pageview_events else Counter()
    devices = Counter(_device_label(event.user_agent) for event in pageview_events)
    sources = Counter(_source_label(event) for event in pageview_events)
    days_counter = Counter(event.created_at.date().isoformat() for event in pageview_events if event.created_at)

    return {
        "updated_label": "обновляется в реальном времени",
        "granularity": "hourly" if days <= 1 else "daily",
        "labels": labels,
        "summary": [
            {
                "label": "Посетители",
                "value": len({event.visitor_id for event in human_events if event.visitor_id}),
                "color": "#4285f4",
                "info": "Уникальные люди без ботов, которых определил наш трекер за выбранный период.",
            },
            {
                "label": "Просмотры",
                "value": len(pageview_events),
                "color": "#673ab7",
                "info": "Все просмотры страниц, которые пришли с установленного JS-кода сайта.",
            },
            {
                "label": "Клики",
                "value": len(click_events),
                "color": "#0f9d58",
                "info": "Нажатия по ссылкам, кнопкам и интерактивным элементам сайта.",
            },
            {
                "label": "Цели",
                "value": len(goal_events),
                "color": "#f59e0b",
                "info": "Целевые действия: формы, заявки, контакты и другие события конверсии.",
            },
        ],
        "series": [
            {"key": "visitors", "label": "Посетители", "color": "#4285f4", "values": [len(visitors_by_bucket.get(label, set())) for label in labels]},
            {"key": "pageviews", "label": "Просмотры", "color": "#673ab7", "values": [pageviews_by_bucket.get(label, 0) for label in labels]},
            {"key": "clicks", "label": "Клики", "color": "#0f9d58", "values": [clicks_by_bucket.get(label, 0) for label in labels]},
            {"key": "goals", "label": "Цели", "color": "#f59e0b", "values": [goals_by_bucket.get(label, 0) for label in labels]},
            {"key": "bots", "label": "Боты", "color": "#64748b", "values": [bots_by_bucket.get(label, 0) for label in labels]},
        ],
        "tabs": [
            {"key": "queries", "label": "Запросы", "metric_label": "Показы", "empty": "Запросы появятся, если поисковик передаст query в referrer или после подключения Google.", "rows": _count_rows(query_counter)},
            {"key": "pages", "label": "Страницы", "metric_label": "Просмотры", "empty": "Пока нет просмотров страниц.", "rows": _count_rows(pages)},
            {"key": "countries", "label": "Страны", "metric_label": "Просмотры", "empty": "Страны появятся после добавления GeoIP или данных Google.", "rows": _count_rows(countries)},
            {"key": "devices", "label": "Устройства", "metric_label": "Просмотры", "empty": "Пока нет данных по устройствам.", "rows": _count_rows(devices)},
            {"key": "search_type", "label": "Вид в поиске", "metric_label": "Просмотры", "empty": "Пока нет источников трафика.", "rows": _count_rows(sources)},
            {"key": "days", "label": "Дни", "metric_label": "Просмотры", "empty": "Пока нет данных по дням.", "rows": _count_rows(days_counter)},
        ],
    }


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


def _is_bot_event(event: Event) -> bool:
    return bool(getattr(event, "is_bot", False))


def _build_bot_stats(bot_events: list[Event]) -> dict[str, Any]:
    bot_names: Counter[tuple[str, str]] = Counter()
    user_agents: Counter[str] = Counter()

    for event in bot_events:
        bot_name = getattr(event, "bot_name", None) or "Unknown bot"
        bot_category = getattr(event, "bot_category", None) or "unknown"
        bot_names[(bot_name, bot_category)] += 1

        user_agent = (getattr(event, "user_agent", None) or "").strip()
        if user_agent:
            user_agents[user_agent[:180]] += 1

    return {
        "total_events": len(bot_events),
        "unique_bots": len({event.visitor_id for event in bot_events if event.visitor_id}),
        "unique_sessions": len({event.session_id for event in bot_events if event.session_id}),
        "known_bots": [
            {"name": name, "category": category, "events": count}
            for (name, category), count in bot_names.most_common(5)
        ],
        "top_user_agents": [
            {"user_agent": user_agent, "events": count}
            for user_agent, count in user_agents.most_common(3)
        ],
    }


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
        empty = _empty_analytics(
            days,
            "Пока недостаточно данных. Система собирает аналитику.",
        )
        empty["realtime_search"] = _build_realtime_search_analytics([], [], days)
        empty["traffic_sources"] = {"items": [], "total": 0}
        empty["utm_campaigns"] = {"items": []}
        return empty

    human_events = [event for event in events if not _is_bot_event(event)]
    bot_events = [event for event in events if _is_bot_event(event)]

    # Для production тяжелые агрегации лучше перенести в SQL-запросы или materialized summaries.
    pageview_events = [event for event in human_events if event.event_type == "pageview"]
    click_events = [event for event in human_events if event.event_type == "click"]
    scroll_events = [event for event in human_events if event.event_type == "scroll"]
    form_submit_events = [event for event in human_events if event.event_type == "form_submit"]
    form_start_events = [event for event in human_events if event.event_type == "form_start"]
    goal_events = [event for event in human_events if event.event_type == "goal"]

    unique_visitors = len({event.visitor_id for event in human_events if event.visitor_id})
    unique_sessions = len({event.session_id for event in human_events if event.session_id})
    click_labels = Counter(_click_label(event) for event in click_events)

    # Подсчет целей: сначала из goal events (tracker v2), затем fallback на click events.
    goal_counts = {"whatsapp": 0, "phone": 0, "email": 0, "cta": 0}
    for event in goal_events:
        meta = _metadata(event)
        goal_type = _lower_value(meta.get("goal_type"))
        if goal_type in goal_counts:
            goal_counts[goal_type] += 1

    # Fallback: если goal events нет, считаем по click events (обратная совместимость).
    if not goal_events:
        goal_counts["whatsapp"] = sum(1 for event in click_events if _is_whatsapp(event))
        goal_counts["phone"] = sum(1 for event in click_events if _is_phone(event))
        goal_counts["email"] = sum(1 for event in click_events if _is_email(event))
        goal_counts["cta"] = sum(1 for event in click_events if _is_cta(event))

    form_starts = len(form_start_events)
    form_submits = len(form_submit_events)
    contact_actions = goal_counts["whatsapp"] + goal_counts["phone"] + goal_counts["email"] + goal_counts["cta"]
    goals_total = contact_actions + form_starts + form_submits

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
            "whatsapp": goal_counts["whatsapp"],
            "phone": goal_counts["phone"],
            "email": goal_counts["email"],
            "cta": goal_counts["cta"],
            "form_starts": form_starts,
            "form_submits": form_submits,
            "total": goals_total,
        },
        "funnel": {
            "site_visits": len(pageview_events),
            "viewed_services": sum(1 for event in pageview_events if _is_services_page(event)),
            "viewed_pricing": sum(1 for event in pageview_events if _is_pricing_page(event)),
            "contact_actions": contact_actions,
            "form_starts": form_starts,
            "form_submits": form_submits,
        },
        "timeseries": _build_timeseries(human_events, days),
        "bots": _build_bot_stats(bot_events),
        "realtime_search": _build_realtime_search_analytics(human_events, bot_events, days),
        "traffic_sources": _build_traffic_sources(pageview_events),
        "utm_campaigns": _build_utm_campaigns(pageview_events),
    }
