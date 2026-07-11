import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai_report import AIReport
from app.models.client import Client
from app.models.event import Event
from app.models.site import Site
from app.repositories.client_repository import ClientRepository
from app.schemas.client import ClientCreate, ClientRead
from app.services.site_score_service import calculate_site_score


class PartnerClientService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.client_repository = ClientRepository(session)

    async def create_client(self, user_id: uuid.UUID, data: ClientCreate) -> ClientRead:
        client = await self.client_repository.create_user_client(user_id, data)
        return ClientRead.model_validate(client)

    async def list_clients_summary(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        clients = await self.client_repository.list_user_clients(user_id)
        rows: list[dict[str, Any]] = []
        for client in clients:
            sites = [site for site in client.sites if site.user_id == user_id]
            site_rows = await self._build_site_rows(sites)
            rows.append(
                {
                    "client": client,
                    "site_count": len(site_rows),
                    "attention_count": sum(1 for row in site_rows if row["needs_attention"]),
                    "last_activity": self._latest_activity_label(site_rows),
                }
            )
        return rows

    async def get_client_detail(self, user_id: uuid.UUID, client_id: uuid.UUID) -> dict[str, Any] | None:
        client = await self.client_repository.get_user_client(user_id, client_id)
        if not client:
            return None
        sites = [site for site in client.sites if site.user_id == user_id]
        site_rows = await self._build_site_rows(sites)
        return {"client": client, "sites": site_rows}

    async def get_user_client_options(self, user_id: uuid.UUID) -> list[ClientRead]:
        clients = await self.client_repository.list_user_clients(user_id)
        return [ClientRead.model_validate(client) for client in clients]

    async def get_partner_overview(self, user_id: uuid.UUID, site_rows: list[dict[str, Any]]) -> dict[str, int]:
        total_sites = len(site_rows)
        return {
            "total_sites": total_sites,
            "attention_sites": sum(1 for row in site_rows if row["needs_attention"]),
            "without_code": sum(1 for row in site_rows if not row["has_tracker_events"]),
            "without_fresh_analysis": sum(1 for row in site_rows if not row["has_fresh_analysis"]),
            "healthy_sites": sum(1 for row in site_rows if row["score"] >= 75),
        }

    async def build_site_rows(self, user_id: uuid.UUID, sites: list[Any]) -> list[dict[str, Any]]:
        site_models = await self._load_site_models(user_id, [site.id for site in sites])
        return await self._build_site_rows(site_models)

    async def _load_site_models(self, user_id: uuid.UUID, site_ids: list[uuid.UUID]) -> list[Site]:
        if not site_ids:
            return []
        result = await self.session.execute(
            select(Site)
            .options(selectinload(Site.client))
            .where(Site.user_id == user_id, Site.id.in_(site_ids))
            .order_by(Site.created_at.desc())
        )
        return list(result.scalars().all())

    async def _build_site_rows(self, sites: list[Site]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        freshness_cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        for site in sites:
            latest_analysis = await self._latest_analysis_at(site.id)
            has_events = await self._has_tracker_events(site.id)
            score = await calculate_site_score(self.session, site.site_id, "7d")
            has_fresh_analysis = bool(latest_analysis and self._as_utc(latest_analysis) >= freshness_cutoff)
            needs_attention = score < 70 or not has_events or not has_fresh_analysis
            rows.append(
                {
                    "site": site,
                    "client": site.client if site.client and site.client.user_id == site.user_id else None,
                    "score": score,
                    "status_label": "Требует внимания" if needs_attention else "В хорошем состоянии",
                    "needs_attention": needs_attention,
                    "has_tracker_events": has_events,
                    "has_fresh_analysis": has_fresh_analysis,
                    "latest_analysis": latest_analysis,
                    "latest_analysis_label": self._format_date(latest_analysis),
                }
            )
        return rows

    async def _latest_analysis_at(self, site_id: uuid.UUID) -> datetime | None:
        result = await self.session.execute(select(func.max(AIReport.created_at)).where(AIReport.site_id == site_id))
        return result.scalar_one_or_none()

    async def _has_tracker_events(self, site_id: uuid.UUID) -> bool:
        result = await self.session.execute(select(func.count()).select_from(Event).where(Event.site_id == site_id))
        return (result.scalar_one() or 0) > 0

    def _latest_activity_label(self, site_rows: list[dict[str, Any]]) -> str:
        latest_dates = [row["latest_analysis"] for row in site_rows if row["latest_analysis"]]
        if not latest_dates:
            return "Пока нет анализа"
        return self._format_date(max(latest_dates))

    def _format_date(self, value: datetime | None) -> str:
        if not value:
            return "Пока нет анализа"
        value = self._as_utc(value)
        today = datetime.now(timezone.utc).date()
        if value.date() == today:
            return "Сегодня"
        if value.date() == today - timedelta(days=1):
            return "Вчера"
        return value.strftime("%d.%m.%Y")

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
