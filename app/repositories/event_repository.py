import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event


class EventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_event(self, event_data: dict) -> Event:
        event = Event(**event_data)
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def list_events_by_site(self, site_id: uuid.UUID, limit: int = 100, offset: int = 0) -> list[Event]:
        result = await self.session.execute(
            select(Event).where(Event.site_id == site_id).order_by(Event.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def count_events_by_site(self, site_id: uuid.UUID) -> int:
        result = await self.session.execute(select(func.count()).select_from(Event).where(Event.site_id == site_id))
        return result.scalar_one()

    async def get_latest_created_at_by_site(self, site_id: uuid.UUID) -> datetime | None:
        # Статус сайта использует только дату последнего события, без вывода visitor/session данных.
        result = await self.session.execute(
            select(func.max(Event.created_at)).where(Event.site_id == site_id)
        )
        return result.scalar_one_or_none()

    async def get_site_event_stats(self, site_id: uuid.UUID) -> dict:
        result = await self.session.execute(
            select(
                Event.event_type,
                func.count().label("count"),
            )
            .where(Event.site_id == site_id)
            .group_by(Event.event_type)
        )
        stats = {row[0]: row[1] for row in result.all()}

        unique_visitors = await self.session.execute(
            select(func.count(func.distinct(Event.visitor_id))).where(Event.site_id == site_id)
        )
        unique_sessions = await self.session.execute(
            select(func.count(func.distinct(Event.session_id))).where(Event.site_id == site_id)
        )
        last_event = await self.session.execute(
            select(Event.created_at).where(Event.site_id == site_id).order_by(Event.created_at.desc()).limit(1)
        )
        last_event_time = last_event.scalar_one_or_none()

        return {
            "total_pageviews": stats.get("pageview", 0),
            "total_clicks": stats.get("click", 0),
            "total_scroll": stats.get("scroll", 0),
            # Показываем новые события трекера в админке, а не только в сырых логах.
            "total_block_views": stats.get("block_view", 0),
            "total_form_submits": stats.get("form_submit", 0),
            "total_time_on_page": stats.get("time_on_page", 0),
            "total_page_leave": stats.get("page_leave", 0),
            "unique_visitors": unique_visitors.scalar_one() or 0,
            "unique_sessions": unique_sessions.scalar_one() or 0,
            "last_event_time": last_event_time,
        }

    async def list_recent_events_by_site(self, site_id: uuid.UUID, limit: int = 10) -> list[Event]:
        result = await self.session.execute(
            select(Event).where(Event.site_id == site_id).order_by(Event.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_events_by_period(self, site_id: uuid.UUID, start: datetime, end: datetime) -> list[Event]:
        result = await self.session.execute(
            select(Event).where(
                Event.site_id == site_id,
                Event.created_at >= start,
                Event.created_at <= end,
            ).order_by(Event.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_event_stats_by_period(self, site_id: uuid.UUID, start: datetime, end: datetime) -> dict:
        result = await self.session.execute(
            select(
                Event.event_type,
                func.count().label("count"),
            )
            .where(
                Event.site_id == site_id,
                Event.created_at >= start,
                Event.created_at <= end,
            )
            .group_by(Event.event_type)
        )
        stats = {row[0]: row[1] for row in result.all()}

        unique_visitors = await self.session.execute(
            select(func.count(func.distinct(Event.visitor_id))).where(
                Event.site_id == site_id,
                Event.created_at >= start,
                Event.created_at <= end,
            )
        )
        unique_sessions = await self.session.execute(
            select(func.count(func.distinct(Event.session_id))).where(
                Event.site_id == site_id,
                Event.created_at >= start,
                Event.created_at <= end,
            )
        )

        total = sum(stats.values())

        return {
            "total": total,
            "pageviews": stats.get("pageview", 0),
            "clicks": stats.get("click", 0),
            "scrolls": stats.get("scroll", 0),
            "block_views": stats.get("block_view", 0),
            "form_submits": stats.get("form_submit", 0),
            "time_on_page": stats.get("time_on_page", 0),
            "page_leave": stats.get("page_leave", 0),
            "unique_visitors": unique_visitors.scalar_one() or 0,
            "unique_sessions": unique_sessions.scalar_one() or 0,
        }

    async def get_click_targets_by_period(self, site_id: uuid.UUID, start: datetime, end: datetime) -> list[dict]:
        result = await self.session.execute(
            select(Event.event_metadata).where(
                Event.site_id == site_id,
                Event.event_type == "click",
                Event.created_at >= start,
                Event.created_at <= end,
            )
        )
        targets = []
        for row in result.scalars().all():
            if row and isinstance(row, dict):
                text = row.get("text", "")
                if text and len(targets) < 50:
                    targets.append({"text": text[:100], "href": row.get("href", ""), "tag": row.get("tag", "")})
        return targets

    async def get_scroll_depth_by_period(self, site_id: uuid.UUID, start: datetime, end: datetime) -> dict:
        result = await self.session.execute(
            select(Event.event_metadata).where(
                Event.site_id == site_id,
                Event.event_type == "scroll",
                Event.created_at >= start,
                Event.created_at <= end,
            )
        )
        depth_counts = {}
        for row in result.scalars().all():
            if row and isinstance(row, dict):
                depth = row.get("depth", 0)
                depth_counts[depth] = depth_counts.get(depth, 0) + 1
        return depth_counts
