from datetime import date, datetime, timedelta, timezone
from typing import Any
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.token_crypto import decode_token
from app.repositories.gsc_repository import GSCRepository
from app.repositories.site_repository import SiteRepository
from app.schemas.gsc import GSCPropertyRead, GSCSummaryRead

logger = logging.getLogger(__name__)


GSC_NOT_CONNECTED_MESSAGE = (
    "Google Search Console пока не подключен. SEO-показы, клики, CTR и позиции будут доступны после подключения."
)
GSC_OAUTH_NOT_CONFIGURED_MESSAGE = "Google OAuth credentials are not configured."
GSC_OAUTH_NOT_CONNECTED_MESSAGE = "Google Search Console OAuth is not connected yet."


class GSCService:
    """Готовит данные Search Console для API, dashboard и AI-отчетов."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.site_repository = SiteRepository(session)
        self.gsc_repository = GSCRepository(session)

    def period_to_dates(self, period: str) -> tuple[str, date, date]:
        normalized = period if period in {"24h", "7d", "30d"} else "7d"
        days = {"24h": 1, "7d": 7, "30d": 30}[normalized]
        end = date.today()
        start = end - timedelta(days=days - 1)
        return normalized, start, end

    async def connect_gsc_property(self, public_site_id: str, property_url: str) -> GSCPropertyRead | None:
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return None

        property_obj = await self.gsc_repository.create_or_update_property(site.id, site.site_id, property_url)
        return GSCPropertyRead.model_validate(property_obj)

    async def list_gsc_properties(self, public_site_id: str) -> dict[str, Any]:
        """Get list of Google Search Console properties accessible to the connected account."""
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return {"status": "error", "message": "Site not found", "properties": []}

        if not settings.google_oauth_configured:
            return {"status": "not_configured", "message": GSC_OAUTH_NOT_CONFIGURED_MESSAGE, "properties": []}

        property_obj = await self.gsc_repository.get_property_by_site(site.id)
        if not property_obj or not property_obj.is_connected:
            return {"status": "not_connected", "message": GSC_OAUTH_NOT_CONNECTED_MESSAGE, "properties": []}

        access_token = decode_token(property_obj.access_token)
        refresh_token = decode_token(property_obj.refresh_token)
        if not access_token:
            await self.gsc_repository.update_last_error(property_obj, "Could not decode access token")
            return {"status": "error", "message": "Could not decode access token. Reconnect Google Search Console.", "properties": []}

        try:
            from app.services.gsc_google_client import GSCGoogleClient

            scopes = property_obj.scopes.split(",") if property_obj.scopes else settings.GOOGLE_SCOPES.split(",")
            credentials = GSCGoogleClient.build_credentials(
                access_token=access_token,
                refresh_token=refresh_token,
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                scopes=scopes,
            )
            properties = GSCGoogleClient.list_sites(credentials)
            return {"status": "ok", "properties": properties}
        except Exception as e:
            logger.error(f"Failed to list GSC properties for site {public_site_id}: {e}")
            error_msg = f"Google API error: {str(e)[:200]}"
            await self.gsc_repository.update_last_error(property_obj, error_msg)
            return {"status": "error", "message": "Failed to fetch Google Search Console properties.", "properties": []}

    async def test_search_analytics_query(
        self,
        public_site_id: str,
        period: str = "7d",
        dimensions: list[str] | None = None,
        row_limit: int = 100,
    ) -> dict[str, Any]:
        """Test Search Analytics query against Google API. Does not save results."""
        if dimensions is None:
            dimensions = ["date", "query", "page"]

        if period == "24h":
            return {
                "status": "unsupported_period",
                "message": "Search Console data is daily. Use 7d or 30d.",
                "rows": [],
            }

        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return {"status": "error", "message": "Site not found", "rows": []}

        if not settings.google_oauth_configured:
            return {"status": "not_configured", "message": GSC_OAUTH_NOT_CONFIGURED_MESSAGE, "rows": []}

        property_obj = await self.gsc_repository.get_property_by_site(site.id)
        if not property_obj or not property_obj.is_connected:
            return {"status": "not_connected", "message": GSC_OAUTH_NOT_CONNECTED_MESSAGE, "rows": []}

        if not property_obj.property_url:
            await self.gsc_repository.update_last_error(property_obj, "GSC property URL is missing")
            return {"status": "missing_property_url", "message": "GSC property URL is missing.", "rows": []}

        access_token = decode_token(property_obj.access_token)
        refresh_token = decode_token(property_obj.refresh_token)
        if not access_token:
            await self.gsc_repository.update_last_error(property_obj, "Could not decode access token")
            return {"status": "error", "message": "Could not decode access token. Reconnect Google Search Console.", "rows": []}

        # GSC data may lag by 1-2 days, use yesterday as end_date.
        yesterday = date.today() - timedelta(days=1)
        days_map = {"7d": 7, "30d": 30}
        days = days_map.get(period, 7)
        start = yesterday - timedelta(days=days - 1)

        try:
            from app.services.gsc_google_client import GSCGoogleClient

            scopes = property_obj.scopes.split(",") if property_obj.scopes else settings.GOOGLE_SCOPES.split(",")
            credentials = GSCGoogleClient.build_credentials(
                access_token=access_token,
                refresh_token=refresh_token,
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                scopes=scopes,
            )
            rows = GSCGoogleClient.query_search_analytics(
                credentials=credentials,
                site_url=property_obj.property_url,
                start_date=start.isoformat(),
                end_date=yesterday.isoformat(),
                dimensions=dimensions,
                row_limit=row_limit,
            )
            return {
                "status": "ok",
                "site_url": property_obj.property_url,
                "period": period,
                "start_date": start.isoformat(),
                "end_date": yesterday.isoformat(),
                "dimensions": dimensions,
                "rows": rows,
            }
        except Exception as e:
            logger.error(f"Search Analytics query failed for site {public_site_id}: {e}")
            error_msg = f"Google API error: {str(e)[:200]}"
            await self.gsc_repository.update_last_error(property_obj, error_msg)
            return {"status": "google_api_error", "message": "Failed to query Google Search Console.", "rows": []}

    async def get_gsc_summary(self, public_site_id: str, period: str = "7d") -> dict[str, Any] | None:
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return None

        normalized, start, end = self.period_to_dates(period)
        property_obj = await self.gsc_repository.get_property_by_site(site.id)
        if not property_obj or not property_obj.is_connected:
            return GSCSummaryRead(
                period=normalized,
                is_connected=False,
                message=GSC_NOT_CONNECTED_MESSAGE,
            ).model_dump()

        summary = await self.gsc_repository.get_summary_by_site_and_period(site.id, start, end)
        return GSCSummaryRead(period=normalized, is_connected=True, **summary).model_dump()

    async def get_gsc_top_queries(self, public_site_id: str, period: str = "7d", limit: int = 10) -> list[dict[str, Any]] | None:
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return None

        _, start, end = self.period_to_dates(period)
        property_obj = await self.gsc_repository.get_property_by_site(site.id)
        if not property_obj or not property_obj.is_connected:
            return []

        return await self.gsc_repository.get_top_queries_by_site_and_period(site.id, start, end, limit=limit)

    async def get_gsc_time_series(self, public_site_id: str, period: str = "7d") -> list[dict[str, Any]] | None:
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return None

        _, start, end = self.period_to_dates(period)
        property_obj = await self.gsc_repository.get_property_by_site(site.id)
        if not property_obj or not property_obj.is_connected:
            return []

        return await self.gsc_repository.get_time_series_by_site_and_period(site.id, start, end)

    async def sync_gsc_data(self, public_site_id: str, period: str = "30d") -> dict[str, Any]:
        """Sync real Google Search Console data to the database."""
        if period == "24h":
            return {
                "status": "unsupported_period",
                "message": "Search Console data is daily. Use 7d or 30d.",
                "site_id": public_site_id,
                "rows_saved": 0,
            }

        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return {"status": "error", "message": "Site not found", "site_id": public_site_id, "rows_saved": 0}

        if not settings.google_oauth_configured:
            return {
                "status": "not_configured",
                "message": GSC_OAUTH_NOT_CONFIGURED_MESSAGE,
                "site_id": public_site_id,
                "rows_saved": 0,
            }

        property_obj = await self.gsc_repository.get_property_by_site(site.id)
        if not property_obj or not property_obj.is_connected:
            return {
                "status": "not_connected",
                "message": GSC_OAUTH_NOT_CONNECTED_MESSAGE,
                "site_id": public_site_id,
                "rows_saved": 0,
            }

        if not property_obj.property_url:
            await self.gsc_repository.update_last_error(property_obj, "GSC property URL is missing")
            return {
                "status": "missing_property_url",
                "message": "GSC property URL is missing.",
                "site_id": public_site_id,
                "rows_saved": 0,
            }

        access_token = decode_token(property_obj.access_token)
        refresh_token = decode_token(property_obj.refresh_token)
        if not access_token:
            await self.gsc_repository.update_last_error(property_obj, "Could not decode access token")
            return {
                "status": "error",
                "message": "Could not decode access token. Reconnect Google Search Console.",
                "site_id": public_site_id,
                "rows_saved": 0,
            }

        # GSC data may lag by 1-2 days, use yesterday as end_date.
        yesterday = date.today() - timedelta(days=1)
        days_map = {"7d": 7, "30d": 30}
        days = days_map.get(period, 30)
        start = yesterday - timedelta(days=days - 1)

        try:
            from app.services.gsc_google_client import GSCGoogleClient

            scopes = property_obj.scopes.split(",") if property_obj.scopes else settings.GOOGLE_SCOPES.split(",")
            credentials = GSCGoogleClient.build_credentials(
                access_token=access_token,
                refresh_token=refresh_token,
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                scopes=scopes,
            )
            rows = GSCGoogleClient.query_search_analytics(
                credentials=credentials,
                site_url=property_obj.property_url,
                start_date=start.isoformat(),
                end_date=yesterday.isoformat(),
                dimensions=["date", "query", "page"],
                row_limit=25000,
            )
        except Exception as e:
            logger.error(f"Search Analytics query failed for site {public_site_id}: {e}")
            error_msg = f"Google API error: {str(e)[:200]}"
            await self.gsc_repository.update_last_error(property_obj, error_msg)
            return {
                "status": "google_api_error",
                "message": "Failed to query Google Search Console.",
                "site_id": public_site_id,
                "rows_saved": 0,
            }

        # Map normalized rows to metric dicts for the repository.
        metrics = []
        for row in rows:
            date_str = row.get("date")
            if not date_str:
                continue
            try:
                metric_date = date.fromisoformat(date_str)
            except (ValueError, TypeError):
                continue
            metrics.append({
                "date": metric_date,
                "query": row.get("query"),
                "page": row.get("page"),
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": row.get("ctr", 0),
                "position": row.get("position", 0),
                "device": row.get("device"),
                "country": row.get("country"),
            })

        # Replace existing metrics for this date range to avoid duplicates.
        saved = await self.gsc_repository.replace_metrics_by_period(
            site.id, site.site_id, start, yesterday, metrics,
        )

        # Update sync state.
        property_obj.last_sync_at = datetime.now(timezone.utc)
        property_obj.last_error = None
        await self.session.commit()

        return {
            "status": "ok",
            "message": "Google Search Console data synced successfully.",
            "site_id": public_site_id,
            "property_url": property_obj.property_url,
            "period": period,
            "start_date": start.isoformat(),
            "end_date": yesterday.isoformat(),
            "rows_fetched": len(rows),
            "rows_saved": len(saved),
            "last_sync_at": property_obj.last_sync_at.isoformat() if property_obj.last_sync_at else None,
        }
