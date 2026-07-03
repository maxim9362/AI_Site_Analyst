from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.ai_report_repository import AIReportRepository
from app.repositories.block_classification_repository import BlockClassificationRepository
from app.repositories.event_repository import EventRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.page_snapshot_repository import PageSnapshotRepository
from app.repositories.site_repository import SiteRepository


def _serialize_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _build_status(
    has_events: bool,
    has_snapshots: bool,
    has_reports: bool,
) -> tuple[str, str, str]:
    # MVP-статус вычисляется по уже существующим данным, без отдельной таблицы задач.
    if has_reports:
        return (
            "ready",
            "Готово",
            "Сайт готов к анализу. Доступен AI-отчет и собранные данные.",
        )

    if has_snapshots:
        return (
            "processing",
            "Идет обработка",
            "Страницы уже сохранены. Система строит базу знаний, классифицирует блоки и готовит данные для отчета.",
        )

    if has_events:
        return (
            "collecting_data",
            "Данные собираются",
            "Система уже получает события посетителей, но структура страниц пока не сохранена.",
        )

    return (
        "no_data",
        "Данных пока нет",
        "Tracker подключен, но система пока не получила события или снимки страниц.",
    )


async def get_site_processing_status(
    db: AsyncSession,
    public_site_id: str,
) -> dict[str, Any] | None:
    site_repository = SiteRepository(db)
    site = await site_repository.get_site_by_site_id(public_site_id)
    if not site:
        return None

    event_repository = EventRepository(db)
    snapshot_repository = PageSnapshotRepository(db)
    knowledge_repository = KnowledgeRepository(db)
    classification_repository = BlockClassificationRepository(db)
    report_repository = AIReportRepository(db)

    events_count = await event_repository.count_events_by_site(site.id)
    snapshots_count = await snapshot_repository.count_snapshots_by_site(site.id)
    knowledge_count = await knowledge_repository.count_chunks_by_site(site.id)
    classifications_count = await classification_repository.count_classifications_by_site(site.id)
    reports_count = await report_repository.count_reports_by_site(site.id)

    has_events = events_count > 0
    has_snapshots = snapshots_count > 0
    has_knowledge = knowledge_count > 0
    has_classifications = classifications_count > 0
    has_reports = reports_count > 0

    status, status_label, message = _build_status(has_events, has_snapshots, has_reports)

    return {
        "site_id": public_site_id,
        "status": status,
        "status_label": status_label,
        "message": message,
        "has_events": has_events,
        "has_snapshots": has_snapshots,
        "has_knowledge": has_knowledge,
        "has_classifications": has_classifications,
        "has_reports": has_reports,
        "last_event_at": _serialize_dt(await event_repository.get_latest_created_at_by_site(site.id)),
        "last_snapshot_at": _serialize_dt(await snapshot_repository.get_latest_created_at_by_site(site.id)),
        "last_knowledge_at": _serialize_dt(await knowledge_repository.get_latest_created_at_by_site(site.id)),
        "last_classification_at": _serialize_dt(await classification_repository.get_latest_created_at_by_site(site.id)),
        "last_report_at": _serialize_dt(await report_repository.get_latest_created_at_by_site(site.id)),
    }
