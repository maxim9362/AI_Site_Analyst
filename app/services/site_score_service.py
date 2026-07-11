from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.block_classification_repository import BlockClassificationRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.gsc_service import GSCService
from app.services.simple_analytics_service import get_simple_site_analytics


def _clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


def _score_label(score: int) -> str:
    if score >= 85:
        return "Сильно"
    if score >= 70:
        return "Хорошо"
    if score >= 40:
        return "Нужно улучшить"
    return "Слабое место"


def _calculate_seo_score(gsc_summary: dict[str, Any] | None) -> tuple[int | None, str, str]:
    """Возвращает (score, message, status). score=None если данных нет."""
    if not gsc_summary or not gsc_summary.get("is_connected"):
        return None, "SEO не оценивался: Google Search Console не подключен или данных пока нет.", "no_data"

    score = 50
    impressions = gsc_summary.get("impressions", 0)
    clicks = gsc_summary.get("clicks", 0)
    ctr = gsc_summary.get("ctr", 0)
    position = gsc_summary.get("position", 0)

    if impressions > 0:
        score += 10
    if clicks > 0:
        score += 10
    if ctr >= 0.10:
        score += 20
    elif ctr >= 0.05:
        score += 10
    if position > 0 and position <= 10:
        score += 15
    elif position > 0 and position <= 20:
        score += 8
    elif position > 30:
        score -= 10

    if impressions > 0 and clicks > 0:
        message = f"CTR {ctr:.1%}, позиция {position:.1f}. "
        if ctr < 0.05:
            message += "CTR можно улучшить через доработку title/description."
        elif position > 20:
            message += "Позиции можно улучшить через доработку контента."
        else:
            message += "Показатели в норме."
    else:
        message = "Данные GSC есть, но показов и кликов пока мало."

    return _clamp(score), message, "ok"


def _calculate_traffic_score(analytics: dict[str, Any] | None) -> tuple[int, str]:
    if not analytics:
        return 20, "Нет данных аналитики."

    visitors = analytics.get("visitors", {})
    pageviews = analytics.get("pageviews", {})
    unique_visitors = visitors.get("unique_visitors", 0)
    total_pageviews = pageviews.get("total", 0)
    top_pages = pageviews.get("top_pages", [])

    if total_pageviews == 0:
        return 20, "Пока нет просмотров страниц."

    score = 45
    if unique_visitors >= 50:
        score += 20
    elif unique_visitors >= 10:
        score += 15
    if top_pages:
        score += 10

    message = f"{total_pageviews} просмотров, {unique_visitors} посетителей."
    if unique_visitors < 10:
        message += " Данных пока немного."
    return _clamp(score), message


def _calculate_conversion_score(analytics: dict[str, Any] | None) -> tuple[int, str]:
    if not analytics:
        return 20, "Нет данных аналитики."

    goals = analytics.get("goals", {})
    funnel = analytics.get("funnel", {})
    total_pageviews = analytics.get("pageviews", {}).get("total", 0)
    goals_total = goals.get("total", 0)
    contact_actions = funnel.get("contact_actions", 0)
    form_starts = funnel.get("form_starts", 0)
    form_submits = funnel.get("form_submits", 0)

    if total_pageviews == 0:
        return 20, "Нет просмотров для оценки конверсии."

    score = 35
    if goals_total > 0:
        score = 55
    if contact_actions > 0:
        score += 15
    if form_starts > 0:
        score += 10
    if form_submits > 0:
        score += 15
    if form_starts > 0 and form_submits == 0:
        score -= 10

    if form_submits > 0:
        message = f"Получено {form_submits} отправок формы. Конверсия работает."
    elif contact_actions > 0:
        message = f"{contact_actions} целевых действий, но формы пока не отправляются."
    elif goals_total > 0:
        message = "Есть целевые действия, но конверсия в заявки низкая."
    else:
        message = "Посетители есть, но целевых действий пока нет."

    return _clamp(score), message


def _calculate_structure_score(
    classifications: list,
    chunks: list,
) -> tuple[int, str]:
    if not classifications and not chunks:
        return 25, "Структура сайта пока не проанализирована."

    if not classifications and chunks:
        return 50, "Данные сайта собраны, но анализ блоков еще не завершен."

    categories = {cls.category for cls in classifications}
    score = 0
    bonuses = {
        "hero": (10, "Главный экран"),
        "services": (15, "Услуги"),
        "contacts": (15, "Контакты"),
        "cta": (15, "CTA"),
        "pricing": (10, "Цены"),
        "faq": (10, "FAQ"),
        "reviews": (10, "Отзывы"),
        "benefits": (8, "Преимущества"),
        "lead_form": (10, "Форма заявки"),
        "about": (7, "О компании"),
    }

    found = []
    for cat, (points, label) in bonuses.items():
        if cat in categories:
            score += points
            found.append(label)

    if found:
        message = f"Найдены блоки: {', '.join(found)}."
    else:
        message = "Классификация есть, но стандартные блоки не обнаружены."

    return _clamp(score), message


def _calculate_trust_score(
    classifications: list,
    chunks: list,
) -> tuple[int, str]:
    if not classifications and not chunks:
        return 20, "Данных для оценки доверия нет."

    categories = {cls.category for cls in classifications} if classifications else set()

    score = 0
    if "contacts" in categories:
        score += 25
    if "reviews" in categories:
        score += 20
    if "faq" in categories:
        score += 15
    if "about" in categories:
        score += 15
    if "pricing" in categories:
        score += 10

    # Проверяем наличие контактов в knowledge chunks.
    all_text = " ".join(chunk.content.lower() for chunk in chunks[:20]) if chunks else ""
    if any(marker in all_text for marker in ("whatsapp", "ватсап", "телефон", "tel:", "phone")):
        score += 15

    if score >= 70:
        message = "На сайте есть контакты, отзывы и основные элементы доверия."
    elif score >= 40:
        message = "Есть базовые элементы, но не хватает отзывов или FAQ."
    else:
        message = "Мало элементов, повышающих доверие клиентов."

    return _clamp(score), message


def _build_quick_wins(
    seo_status: str,
    seo_score: int | None,
    traffic_score: int,
    conversion_score: int,
    structure_score: int,
    trust_score: int,
    categories: set,
    analytics: dict[str, Any] | None,
) -> list[str]:
    wins = []

    if seo_status == "no_data":
        wins.append("Подключить Google Search Console, чтобы оценивать SEO по реальным данным")
    elif seo_score is not None and seo_score < 70:
        wins.append("Улучшить title/description для запросов с показами в Google")

    if conversion_score < 60:
        wins.append("Добавить заметную кнопку после блока услуг")
    if "pricing" not in categories:
        wins.append("Добавить блок цен или объяснить, от чего зависит стоимость")
    if "faq" not in categories:
        wins.append("Добавить FAQ с частыми вопросами клиентов")
    if "reviews" not in categories:
        wins.append("Добавить отзывы клиентов для повышения доверия")
    if trust_score < 50:
        wins.append("Добавить информацию о компании и контакты")

    goals = (analytics or {}).get("goals", {})
    if goals.get("form_starts", 0) > 0 and goals.get("form_submits", 0) == 0:
        wins.append("Упростить форму заявки — пользователи начинают, но не отправляют")

    if not wins:
        wins.append("Продолжать собирать данные для более точных рекомендаций")

    return wins[:5]


async def calculate_site_score(
    db: AsyncSession,
    public_site_id: str,
    period: str = "7d",
) -> dict[str, Any]:
    """Вычисляет оценку сайта 0–100 на основе собранных данных."""
    from app.repositories.site_repository import SiteRepository

    site_repository = SiteRepository(db)
    site = await site_repository.get_site_by_site_id(public_site_id)
    if not site:
        return {"error": "Site not found"}

    # Нормализуем period.
    normalized = period if period in {"24h", "7d", "30d"} else "7d"
    days_map = {"24h": 1, "7d": 7, "30d": 30}
    days = days_map[normalized]

    # Собираем данные.
    analytics = await get_simple_site_analytics(db, public_site_id, days=days)
    gsc_service = GSCService(db)
    # GSC не поддерживает 24h — данные дневные.
    if normalized == "24h":
        gsc_summary = {
            "period": normalized,
            "is_connected": False,
            "message": "SEO не оценивался: Google Search Console доступен только для периодов 7 дней и 30 дней.",
            "clicks": 0,
            "impressions": 0,
            "ctr": 0.0,
            "position": 0.0,
        }
    else:
        gsc_summary = await gsc_service.get_gsc_summary(public_site_id, normalized)

    classification_repository = BlockClassificationRepository(db)
    knowledge_repository = KnowledgeRepository(db)
    classifications = await classification_repository.list_classifications_by_site(site.id, limit=50)
    chunks = await knowledge_repository.list_chunks_by_site(site.id, limit=50)

    # Считаем scores.
    seo_score, seo_msg, seo_status = _calculate_seo_score(gsc_summary)
    traffic_score, traffic_msg = _calculate_traffic_score(analytics)
    conversion_score, conversion_msg = _calculate_conversion_score(analytics)
    structure_score, structure_msg = _calculate_structure_score(classifications, chunks)
    trust_score, trust_msg = _calculate_trust_score(classifications, chunks)

    # Overall считается только по категориям с реальными данными.
    scores_with_data = [
        s for s in [seo_score, traffic_score, conversion_score, structure_score, trust_score]
        if s is not None
    ]
    if scores_with_data:
        overall = round(sum(scores_with_data) / len(scores_with_data))
        overall = _clamp(overall)
        overall_label = _score_label(overall)
        overall_message = f"Сайт получает оценку {overall}/100."
    else:
        overall = None
        overall_label = "Недостаточно данных"
        overall_message = "Пока недостаточно данных для общей оценки сайта."

    categories = {cls.category for cls in classifications} if classifications else set()
    quick_wins = _build_quick_wins(
        seo_status, seo_score, traffic_score, conversion_score, structure_score, trust_score,
        categories, analytics,
    )

    return {
        "overall_score": overall,
        "label": overall_label,
        "message": overall_message,
        "scores": {
            "seo": {"status": seo_status, "score": seo_score, "label": "SEO", "message": seo_msg},
            "traffic": {"status": "ok", "score": traffic_score, "label": "Трафик", "message": traffic_msg},
            "conversion": {"status": "ok", "score": conversion_score, "label": "Конверсия", "message": conversion_msg},
            "structure": {"status": "ok", "score": structure_score, "label": "Структура сайта", "message": structure_msg},
            "trust": {"status": "ok", "score": trust_score, "label": "Доверие", "message": trust_msg},
        },
        "quick_wins": quick_wins,
    }
