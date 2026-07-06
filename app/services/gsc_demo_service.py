import random
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.gsc_repository import GSCRepository
from app.repositories.site_repository import SiteRepository

DEMO_QUERIES = [
    "нотариус ашдод",
    "нотариальные услуги",
    "доверенность на русском",
    "заверение документов",
    "нотариальный перевод",
    "апостиль документы",
    "нотариус рядом",
]

DEMO_PAGES = [
    "/",
    "/services",
    "/prices",
    "/contacts",
    "/faq",
]

DEVICES = ["desktop", "mobile"]
COUNTRY = "ISR"


def _clamp_days(days: int) -> int:
    if days < 7:
        return 7
    if days > 90:
        return 90
    return days


def _generate_demo_metrics(days: int) -> list[dict[str, Any]]:
    """Генерирует demo GSC metrics за последние days дней.

    Возвращает dicts только с данными метрик — site_id и public_site_id
    добавляются repository при сохранении.
    """
    today = date.today()
    metrics = []

    for offset in range(days):
        day = today - timedelta(days=days - 1 - offset)
        # impressions растут ближе к текущей дате.
        growth_factor = 0.6 + 0.4 * (offset / max(days - 1, 1))

        for query in DEMO_QUERIES:
            page = random.choice(DEMO_PAGES)
            device = random.choice(DEVICES)

            base_impressions = random.randint(40, 200)
            impressions = int(base_impressions * growth_factor)
            position = round(random.uniform(5, 35), 1)
            # CTR снижается с ростом позиции (чем выше номер — тем хуже позиция).
            ctr_base = max(0.02, 0.12 - position * 0.002)
            ctr = round(ctr_base * random.uniform(0.7, 1.3), 4)
            clicks = max(0, int(impressions * ctr))

            metrics.append({
                "date": day,
                "query": query,
                "page": page,
                "clicks": clicks,
                "impressions": impressions,
                "ctr": round(clicks / impressions, 4) if impressions else 0.0,
                "position": position,
                "device": device,
                "country": COUNTRY,
            })

    return metrics


async def create_demo_gsc_data(
    db: AsyncSession,
    public_site_id: str,
    days: int = 30,
) -> dict[str, Any]:
    """Создаёт demo GSC данные для сайта. Только для локальной разработки."""
    days = _clamp_days(days)
    site_repository = SiteRepository(db)
    gsc_repository = GSCRepository(db)

    site = await site_repository.get_site_by_site_id(public_site_id)
    if not site:
        return {"status": "error", "message": "Site not found"}

    # Создаём или обновляем property.
    property_url = f"https://{site.domain}/" if "." in site.domain else f"https://localhost/"
    property_obj = await gsc_repository.create_or_update_property(site.id, site.site_id, property_url)
    property_obj.is_connected = True
    property_obj.last_sync_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(property_obj)

    # Удаляем старые demo metrics и создаём новые.
    await gsc_repository.delete_metrics_by_site(site.id)
    metrics = _generate_demo_metrics(days)
    await gsc_repository.save_search_metrics_bulk(site.id, site.site_id, metrics)

    return {
        "status": "ok",
        "message": "Demo Google Search Console data created",
        "site_id": public_site_id,
        "property_url": property_url,
        "days": days,
        "rows_created": len(metrics),
    }
