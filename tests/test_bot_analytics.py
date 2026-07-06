import unittest
from pathlib import Path
from types import SimpleNamespace

from app.core.bot_detection import detect_bot
from app.services.simple_analytics_service import _build_bot_stats


class BotDetectionTests(unittest.TestCase):
    def test_googlebot_is_detected(self):
        result = detect_bot("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")

        self.assertTrue(result["is_bot"])
        self.assertEqual(result["bot_name"], "Googlebot")
        self.assertEqual(result["bot_category"], "search_engine")

    def test_seo_bot_is_detected(self):
        result = detect_bot("Mozilla/5.0 AhrefsBot/7.0")

        self.assertTrue(result["is_bot"])
        self.assertEqual(result["bot_name"], "AhrefsBot")
        self.assertEqual(result["bot_category"], "seo_tool")

    def test_human_browser_is_not_bot(self):
        result = detect_bot(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "Chrome/126.0.0.0 Safari/537.36"
        )

        self.assertFalse(result["is_bot"])
        self.assertIsNone(result["bot_name"])


class BotAnalyticsSourceTests(unittest.TestCase):
    def test_event_route_passes_request_identity_to_service(self):
        route_source = Path("app/api/routes/events.py").read_text(encoding="utf-8")

        self.assertIn('request.headers.get("user-agent")', route_source)
        self.assertIn("ip_address=request.client.host if request.client else None", route_source)

    def test_event_schema_and_model_include_bot_fields(self):
        schema_source = Path("app/schemas/event.py").read_text(encoding="utf-8")
        model_source = Path("app/models/event.py").read_text(encoding="utf-8")

        for field_name in ("user_agent", "ip_address", "is_bot", "bot_name", "bot_category"):
            self.assertIn(field_name, schema_source)
            self.assertIn(field_name, model_source)

    def test_dashboards_show_bot_column(self):
        user_template = Path("app/templates/user_site_dashboard.html").read_text(encoding="utf-8")
        admin_template = Path("app/templates/admin_site_detail.html").read_text(encoding="utf-8")

        self.assertIn("dashboard.tracker_analytics.bots.unique_bots", user_template)
        self.assertIn("dashboard.tracker_analytics.bots.known_bots", user_template)
        self.assertIn("dashboard.tracker_analytics.bots.unique_bots", admin_template)


class BotSummaryTests(unittest.TestCase):
    def test_bot_summary_groups_bots_and_user_agents(self):
        events = [
            SimpleNamespace(
                visitor_id="bot-1",
                session_id="session-1",
                bot_name="Googlebot",
                bot_category="search_engine",
                user_agent="Googlebot/2.1",
            ),
            SimpleNamespace(
                visitor_id="bot-1",
                session_id="session-1",
                bot_name="Googlebot",
                bot_category="search_engine",
                user_agent="Googlebot/2.1",
            ),
            SimpleNamespace(
                visitor_id="bot-2",
                session_id="session-2",
                bot_name="AhrefsBot",
                bot_category="seo_tool",
                user_agent="AhrefsBot/7.0",
            ),
        ]

        summary = _build_bot_stats(events)

        self.assertEqual(summary["total_events"], 3)
        self.assertEqual(summary["unique_bots"], 2)
        self.assertEqual(summary["unique_sessions"], 2)
        self.assertEqual(summary["known_bots"][0], {"name": "Googlebot", "category": "search_engine", "events": 2})
