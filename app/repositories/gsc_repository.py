import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gsc_property import GSCProperty
from app.models.gsc_search_metric import GSCSearchMetric


class GSCRepository:
    """Работает только с хранением GSC-данных, без знаний о Google API."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_or_update_property(
        self,
        site_id: uuid.UUID,
        public_site_id: str,
        property_url: str,
    ) -> GSCProperty:
        property_obj = await self.get_property_by_site(site_id)
        if property_obj:
            property_obj.property_url = property_url
            await self.session.commit()
            await self.session.refresh(property_obj)
            return property_obj

        property_obj = GSCProperty(
            site_id=site_id,
            public_site_id=public_site_id,
            property_url=property_url,
            is_connected=False,
        )
        self.session.add(property_obj)
        await self.session.commit()
        await self.session.refresh(property_obj)
        return property_obj

    async def get_property_by_site(self, site_id: uuid.UUID) -> GSCProperty | None:
        result = await self.session.execute(select(GSCProperty).where(GSCProperty.site_id == site_id))
        return result.scalar_one_or_none()

    async def update_oauth_tokens(
        self,
        property_obj: GSCProperty,
        *,
        access_token: str | None,
        refresh_token: str | None,
        token_expires_at: datetime | None,
        scopes: str | None,
        google_account_email: str | None,
    ) -> GSCProperty:
        property_obj.access_token = access_token
        property_obj.refresh_token = refresh_token
        property_obj.token_expires_at = token_expires_at
        property_obj.scopes = scopes
        property_obj.google_account_email = google_account_email
        property_obj.is_connected = True
        property_obj.last_error = None
        await self.session.commit()
        await self.session.refresh(property_obj)
        return property_obj

    async def update_last_error(self, property_obj: GSCProperty, error: str | None) -> GSCProperty:
        property_obj.last_error = error
        if error:
            property_obj.is_connected = False
        await self.session.commit()
        await self.session.refresh(property_obj)
        return property_obj

    async def update_last_sync_at(self, property_obj: GSCProperty, sync_time: datetime) -> GSCProperty:
        property_obj.last_sync_at = sync_time
        await self.session.commit()
        await self.session.refresh(property_obj)
        return property_obj

    async def delete_metrics_by_site(self, site_id: uuid.UUID) -> None:
        # For development only. In production do not delete real GSC metrics.
        await self.session.execute(delete(GSCSearchMetric).where(GSCSearchMetric.site_id == site_id))
        await self.session.commit()

    async def save_search_metrics_bulk(
        self,
        site_id: uuid.UUID,
        public_site_id: str,
        metrics: list[dict[str, Any]],
    ) -> list[GSCSearchMetric]:
        metric_objects = [
            GSCSearchMetric(site_id=site_id, public_site_id=public_site_id, **metric)
            for metric in metrics
        ]
        self.session.add_all(metric_objects)
        await self.session.commit()
        return metric_objects

    async def replace_metrics_by_period(
        self,
        site_id: uuid.UUID,
        public_site_id: str,
        period_start: date,
        period_end: date,
        metrics: list[dict[str, Any]],
    ) -> list[GSCSearchMetric]:
        # При будущей синхронизации период будет перезаписываться, чтобы не плодить дубли.
        await self.session.execute(
            delete(GSCSearchMetric).where(
                GSCSearchMetric.site_id == site_id,
                GSCSearchMetric.date >= period_start,
                GSCSearchMetric.date <= period_end,
            )
        )
        return await self.save_search_metrics_bulk(site_id, public_site_id, metrics) if metrics else []

    async def list_metrics_by_site_and_period(
        self,
        site_id: uuid.UUID,
        period_start: date,
        period_end: date,
    ) -> list[GSCSearchMetric]:
        result = await self.session.execute(
            select(GSCSearchMetric)
            .where(
                GSCSearchMetric.site_id == site_id,
                GSCSearchMetric.date >= period_start,
                GSCSearchMetric.date <= period_end,
            )
            .order_by(GSCSearchMetric.date.asc())
        )
        return list(result.scalars().all())

    async def get_summary_by_site_and_period(
        self,
        site_id: uuid.UUID,
        period_start: date,
        period_end: date,
    ) -> dict[str, Any]:
        result = await self.session.execute(
            select(
                func.coalesce(func.sum(GSCSearchMetric.clicks), 0),
                func.coalesce(func.sum(GSCSearchMetric.impressions), 0),
                func.coalesce(func.avg(GSCSearchMetric.position), 0.0),
            ).where(
                GSCSearchMetric.site_id == site_id,
                GSCSearchMetric.date >= period_start,
                GSCSearchMetric.date <= period_end,
            )
        )
        clicks, impressions, position = result.one()
        clicks = int(clicks or 0)
        impressions = int(impressions or 0)
        return {
            "clicks": clicks,
            "impressions": impressions,
            "ctr": round(clicks / impressions, 4) if impressions else 0.0,
            "position": round(float(position or 0.0), 2),
        }

    async def get_top_queries_by_site_and_period(
        self,
        site_id: uuid.UUID,
        period_start: date,
        period_end: date,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(
                GSCSearchMetric.query,
                func.coalesce(func.sum(GSCSearchMetric.clicks), 0).label("clicks"),
                func.coalesce(func.sum(GSCSearchMetric.impressions), 0).label("impressions"),
                func.coalesce(func.avg(GSCSearchMetric.position), 0.0).label("position"),
            )
            .where(
                GSCSearchMetric.site_id == site_id,
                GSCSearchMetric.date >= period_start,
                GSCSearchMetric.date <= period_end,
                GSCSearchMetric.query.is_not(None),
            )
            .group_by(GSCSearchMetric.query)
            .order_by(func.sum(GSCSearchMetric.impressions).desc())
            .limit(limit)
        )
        queries = []
        for query, clicks, impressions, position in result.all():
            clicks = int(clicks or 0)
            impressions = int(impressions or 0)
            queries.append({
                "query": query,
                "clicks": clicks,
                "impressions": impressions,
                "ctr": round(clicks / impressions, 4) if impressions else 0.0,
                "position": round(float(position or 0.0), 2),
            })
        return queries

    async def get_time_series_by_site_and_period(
        self,
        site_id: uuid.UUID,
        period_start: date,
        period_end: date,
    ) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(
                GSCSearchMetric.date,
                func.coalesce(func.sum(GSCSearchMetric.clicks), 0).label("clicks"),
                func.coalesce(func.sum(GSCSearchMetric.impressions), 0).label("impressions"),
                func.coalesce(func.avg(GSCSearchMetric.position), 0.0).label("position"),
            )
            .where(
                GSCSearchMetric.site_id == site_id,
                GSCSearchMetric.date >= period_start,
                GSCSearchMetric.date <= period_end,
            )
            .group_by(GSCSearchMetric.date)
            .order_by(GSCSearchMetric.date.asc())
        )
        points = []
        for day, clicks, impressions, position in result.all():
            clicks = int(clicks or 0)
            impressions = int(impressions or 0)
            points.append({
                "date": day.isoformat(),
                "clicks": clicks,
                "impressions": impressions,
                "ctr": round(clicks / impressions, 4) if impressions else 0.0,
                "position": round(float(position or 0.0), 2),
            })
        return points
