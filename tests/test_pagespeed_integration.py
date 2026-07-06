import unittest
from pathlib import Path
from types import SimpleNamespace

from app.services.pagespeed_service import PageSpeedService


class PageSpeedServiceTests(unittest.TestCase):
    def test_build_target_url_adds_https_when_scheme_is_missing(self):
        service = PageSpeedService(None)

        self.assertEqual(service.build_target_url("example.com"), "https://example.com")
        self.assertEqual(service.build_target_url("https://example.com"), "https://example.com")

    def test_normalize_response_extracts_scores_metrics_and_opportunities(self):
        service = PageSpeedService(None)
        site = SimpleNamespace(id="site-db-id", site_id="site_public")
        raw = {
            "id": "https://example.com/",
            "lighthouseResult": {
                "categories": {
                    "performance": {"score": 0.91},
                    "accessibility": {"score": 0.88},
                    "best-practices": {"score": 0.77},
                    "seo": {"score": 1},
                },
                "audits": {
                    "first-contentful-paint": {"score": 0.9, "displayValue": "1.2 s", "numericValue": 1200},
                    "largest-contentful-paint": {"score": 0.5, "displayValue": "3.1 s", "numericValue": 3100},
                    "total-blocking-time": {"score": 1, "displayValue": "0 ms", "numericValue": 0},
                    "cumulative-layout-shift": {"score": 1, "displayValue": "0", "numericValue": 0},
                    "speed-index": {"score": 0.6, "displayValue": "4.2 s", "numericValue": 4200},
                    "unused-javascript": {
                        "title": "Reduce unused JavaScript",
                        "score": 0,
                        "displayValue": "120 KiB",
                        "scoreDisplayMode": "numeric",
                        "details": {"type": "opportunity", "overallSavingsMs": 900},
                    },
                },
            },
        }

        result = service.normalize_response(raw, site=site, target_url="https://example.com", strategy="mobile")

        self.assertEqual(result["performance_score"], 91.0)
        self.assertEqual(result["seo_score"], 100.0)
        self.assertEqual(result["metrics"]["largest-contentful-paint"]["display_value"], "3.1 s")
        self.assertEqual(result["opportunities"][0]["id"], "unused-javascript")


class PageSpeedSourceTests(unittest.TestCase):
    def test_pagespeed_migration_exists(self):
        migration = Path("migrations/versions/012_create_pagespeed_results.py").read_text(encoding="utf-8")

        self.assertIn('revision: str = "012"', migration)
        self.assertIn('"pagespeed_results"', migration)
        self.assertIn('"performance_score"', migration)
        self.assertIn('"opportunities"', migration)

    def test_pagespeed_dashboard_and_ai_context_are_wired(self):
        dashboard_source = Path("app/templates/user_site_dashboard.html").read_text(encoding="utf-8")
        route_source = Path("app/auth/routes.py").read_text(encoding="utf-8")
        ai_report_source = Path("app/services/ai_report_service.py").read_text(encoding="utf-8")

        self.assertIn("PageSpeed Insights", dashboard_source)
        self.assertIn('action="/sites/{{ site.site_id }}/pagespeed/run"', dashboard_source)
        self.assertIn('@router.post("/sites/{site_id}/pagespeed/run")', route_source)
        self.assertIn("PageSpeedService(db).run_pagespeed", route_source)
        self.assertIn("PAGESPEED INSIGHTS", ai_report_source)
        self.assertIn("pagespeed_service.get_ai_context", ai_report_source)
