"""Google Search Console API client.

Thin wrapper around google-api-python-client for GSC operations.
Does not depend on SQLAlchemy, models, or repositories.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


class GSCGoogleClient:
    """Synchronous Google Search Console API client.

    For production with high volumes, consider moving API calls
    to background tasks or thread pool.
    """

    @staticmethod
    def build_credentials(
        access_token: str,
        refresh_token: str | None,
        client_id: str,
        client_secret: str,
        scopes: list[str],
    ):
        """Create Google OAuth2 Credentials object."""
        from google.oauth2.credentials import Credentials

        return Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=GOOGLE_TOKEN_URI,
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
        )

    @staticmethod
    def list_sites(credentials) -> list[dict[str, Any]]:
        """Get list of Google Search Console properties accessible to the account.

        Returns list of dicts with site_url and permission_level.
        """
        from googleapiclient.discovery import build

        service = build("searchconsole", "v1", credentials=credentials)
        response = service.sites().list().execute()
        entries = response.get("siteEntry", [])
        return [
            {
                "site_url": entry.get("siteUrl", ""),
                "permission_level": entry.get("permissionLevel", ""),
            }
            for entry in entries
        ]

    @staticmethod
    def query_search_analytics(
        credentials,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: list[str],
        row_limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Query Google Search Console Search Analytics API.

        Args:
            credentials: Google OAuth2 Credentials object.
            site_url: GSC property URL (e.g. "https://example.com/").
            start_date: Start date as "YYYY-MM-DD".
            end_date: End date as "YYYY-MM-DD".
            dimensions: List of dimensions (e.g. ["date", "query", "page"]).
            row_limit: Max rows to return (default 1000, max 25000).

        Returns:
            List of normalized row dicts with keys matching dimensions + metrics.
        """
        from googleapiclient.discovery import build

        service = build("searchconsole", "v1", credentials=credentials)

        request_body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimensions,
            "rowLimit": min(row_limit, 25000),
        }

        response = (
            service.searchanalytics()
            .query(siteUrl=site_url, body=request_body)
            .execute()
        )

        rows = response.get("rows", [])
        result = []
        for row in rows:
            keys = row.get("keys", [])
            item: dict[str, Any] = {
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round(row.get("ctr", 0), 4),
                "position": round(row.get("position", 0), 1),
            }
            for index, dimension in enumerate(dimensions):
                item[dimension] = keys[index] if index < len(keys) else None
            result.append(item)

        return result
