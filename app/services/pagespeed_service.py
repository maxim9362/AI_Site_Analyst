import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.pagespeed_repository import PageSpeedRepository
from app.repositories.site_repository import SiteRepository
from app.schemas.pagespeed import PageSpeedResultRead


PAGESPEED_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
PAGESPEED_CATEGORIES = ["performance", "accessibility", "best-practices", "seo"]
PAGESPEED_METRICS = {
    "first-contentful-paint": "FCP",
    "largest-contentful-paint": "LCP",
    "total-blocking-time": "TBT",
    "cumulative-layout-shift": "CLS",
    "speed-index": "Speed Index",
}


class PageSpeedService:
    def __init__(self, session: AsyncSession):
        self.site_repository = SiteRepository(session)
        self.pagespeed_repository = PageSpeedRepository(session)

    def normalize_strategy(self, strategy: str) -> str:
        return strategy if strategy in {"mobile", "desktop"} else "mobile"

    def build_target_url(self, domain: str) -> str:
        normalized = domain.strip()
        if normalized.startswith(("http://", "https://")):
            return normalized
        return f"https://{normalized}"

    def _score(self, categories: dict[str, Any], key: str) -> float | None:
        raw = categories.get(key, {}).get("score")
        if raw is None:
            return None
        return round(float(raw) * 100, 1)

    def _extract_metrics(self, audits: dict[str, Any]) -> dict[str, dict[str, Any]]:
        metrics = {}
        for audit_key, label in PAGESPEED_METRICS.items():
            audit = audits.get(audit_key, {})
            metrics[audit_key] = {
                "label": label,
                "score": audit.get("score"),
                "display_value": audit.get("displayValue"),
                "numeric_value": audit.get("numericValue"),
            }
        return metrics

    def _extract_opportunities(self, audits: dict[str, Any]) -> list[dict[str, Any]]:
        opportunities = []
        for audit_id, audit in audits.items():
            details = audit.get("details") or {}
            if details.get("type") != "opportunity":
                continue
            savings = details.get("overallSavingsMs") or 0
            if audit.get("score") == 1 and not savings:
                continue
            opportunities.append({
                "id": audit_id,
                "title": audit.get("title"),
                "display_value": audit.get("displayValue"),
                "score": audit.get("score"),
                "overall_savings_ms": savings,
            })
        return sorted(opportunities, key=lambda item: item.get("overall_savings_ms") or 0, reverse=True)[:8]

    def _extract_diagnostics(self, audits: dict[str, Any]) -> list[dict[str, Any]]:
        diagnostics = []
        for audit_id, audit in audits.items():
            score = audit.get("score")
            if score is None or score == 1:
                continue
            if audit.get("scoreDisplayMode") not in {"binary", "numeric"}:
                continue
            diagnostics.append({
                "id": audit_id,
                "title": audit.get("title"),
                "display_value": audit.get("displayValue"),
                "score": score,
            })
        return diagnostics[:12]

    def normalize_response(self, raw: dict[str, Any], *, site, target_url: str, strategy: str) -> dict[str, Any]:
        lighthouse = raw.get("lighthouseResult") or {}
        categories = lighthouse.get("categories") or {}
        audits = lighthouse.get("audits") or {}
        return {
            "site_id": site.id,
            "public_site_id": site.site_id,
            "url": raw.get("id") or lighthouse.get("finalUrl") or target_url,
            "strategy": strategy,
            "fetched_at": datetime.now(timezone.utc),
            "performance_score": self._score(categories, "performance"),
            "accessibility_score": self._score(categories, "accessibility"),
            "best_practices_score": self._score(categories, "best-practices"),
            "seo_score": self._score(categories, "seo"),
            "metrics": self._extract_metrics(audits),
            "opportunities": self._extract_opportunities(audits),
            "diagnostics": self._extract_diagnostics(audits),
            "error": None,
        }

    def _fetch_pagespeed_sync(self, target_url: str, strategy: str) -> dict[str, Any]:
        params: list[tuple[str, str]] = [("url", target_url), ("strategy", strategy), ("locale", "ru")]
        params.extend(("category", category) for category in PAGESPEED_CATEGORIES)
        if settings.PAGESPEED_API_KEY:
            params.append(("key", settings.PAGESPEED_API_KEY))
        url = f"{PAGESPEED_ENDPOINT}?{urlencode(params)}"
        request = Request(url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    async def fetch_pagespeed_data(self, target_url: str, strategy: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._fetch_pagespeed_sync, target_url, strategy)

    async def run_pagespeed(self, public_site_id: str, strategy: str = "mobile") -> PageSpeedResultRead | None:
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return None

        normalized_strategy = self.normalize_strategy(strategy)
        target_url = self.build_target_url(site.domain)
        try:
            raw = await self.fetch_pagespeed_data(target_url, normalized_strategy)
            data = self.normalize_response(raw, site=site, target_url=target_url, strategy=normalized_strategy)
        except Exception as exc:
            data = {
                "site_id": site.id,
                "public_site_id": site.site_id,
                "url": target_url,
                "strategy": normalized_strategy,
                "fetched_at": datetime.now(timezone.utc),
                "performance_score": None,
                "accessibility_score": None,
                "best_practices_score": None,
                "seo_score": None,
                "metrics": None,
                "opportunities": [],
                "diagnostics": [],
                "error": str(exc)[:500],
            }

        result = await self.pagespeed_repository.create_result(data)
        return PageSpeedResultRead.model_validate(result)

    async def get_latest_by_site(self, public_site_id: str) -> dict[str, PageSpeedResultRead]:
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return {}
        latest = await self.pagespeed_repository.list_latest_by_site(site.id)
        return {strategy: PageSpeedResultRead.model_validate(result) for strategy, result in latest.items()}

    async def get_ai_context(self, public_site_id: str) -> dict[str, Any]:
        latest = await self.get_latest_by_site(public_site_id)
        return {
            strategy: result.model_dump(mode="json")
            for strategy, result in latest.items()
        }
