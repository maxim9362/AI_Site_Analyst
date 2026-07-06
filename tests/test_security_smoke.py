import asyncio
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import HTTPException
from starlette.requests import Request

from app.core import admin_auth
from app.core.config import Settings, settings
from app.services import gsc_oauth_service
from app.services.demo_page_service import render_demo_html, validate_demo_site_id


class SettingsGuardTests(unittest.TestCase):
    def test_local_settings_do_not_raise(self):
        Settings(APP_ENV="local").validate_production_settings()

    def test_unsafe_production_settings_raise_with_all_required_items(self):
        with self.assertRaisesRegex(RuntimeError, "Unsafe production settings") as ctx:
            Settings(APP_ENV="production").validate_production_settings()

        message = str(ctx.exception)
        self.assertIn("DEBUG must be false", message)
        self.assertIn("ADMIN_DASHBOARD_PASSWORD", message)
        self.assertIn("ADMIN_SESSION_SECRET", message)
        self.assertIn("ADMIN_API_KEY", message)
        self.assertIn("ENABLE_DEMO_ENDPOINTS", message)
        self.assertIn("ALLOWED_ORIGINS", message)
        self.assertIn("TOKEN_ENCRYPTION_KEY", message)
        self.assertIn("APP_BASE_URL", message)

    def test_safe_production_settings_pass(self):
        safe_settings = Settings(
            APP_ENV="production",
            DEBUG=False,
            SQL_ECHO=False,
            APP_BASE_URL="https://app.example",
            ADMIN_DASHBOARD_PASSWORD="strong_password",
            ADMIN_SESSION_SECRET="strong_session_secret",
            ADMIN_API_KEY="",
            ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE=10,
            ENABLE_DEMO_ENDPOINTS=False,
            ALLOWED_ORIGINS="https://client.example",
            TOKEN_ENCRYPTION_KEY="0_WQ-TuO8XxWhw-Nwb04Gq8X0YVYEWpbA3QzSShW610=",
        )

        safe_settings.validate_production_settings()

    def test_production_rejects_invalid_admin_login_rate_limit(self):
        unsafe_settings = Settings(
            APP_ENV="production",
            DEBUG=False,
            SQL_ECHO=False,
            APP_BASE_URL="https://app.example",
            ADMIN_DASHBOARD_PASSWORD="strong_password",
            ADMIN_SESSION_SECRET="strong_session_secret",
            ADMIN_API_KEY="",
            ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE=0,
            ENABLE_DEMO_ENDPOINTS=False,
            ALLOWED_ORIGINS="https://client.example",
            TOKEN_ENCRYPTION_KEY="0_WQ-TuO8XxWhw-Nwb04Gq8X0YVYEWpbA3QzSShW610=",
        )

        with self.assertRaisesRegex(RuntimeError, "ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE"):
            unsafe_settings.validate_production_settings()


class AdminAuthTests(unittest.TestCase):
    def setUp(self):
        self.original_password = settings.ADMIN_DASHBOARD_PASSWORD
        self.original_secret = settings.ADMIN_SESSION_SECRET
        self.original_api_key = settings.ADMIN_API_KEY
        self.original_ttl = settings.ADMIN_SESSION_TTL_SECONDS
        self.original_login_rate_limit = settings.ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE
        settings.ADMIN_DASHBOARD_PASSWORD = "test_password"
        settings.ADMIN_SESSION_SECRET = "test_secret"
        settings.ADMIN_API_KEY = "test_api_key"
        settings.ADMIN_SESSION_TTL_SECONDS = 3600
        settings.ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE = 10

    def tearDown(self):
        settings.ADMIN_DASHBOARD_PASSWORD = self.original_password
        settings.ADMIN_SESSION_SECRET = self.original_secret
        settings.ADMIN_API_KEY = self.original_api_key
        settings.ADMIN_SESSION_TTL_SECONDS = self.original_ttl
        settings.ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE = self.original_login_rate_limit

    def _request_with_cookie(self, cookie: str = "") -> Request:
        headers = []
        if cookie:
            headers.append((b"cookie", cookie.encode()))
        return Request({"type": "http", "headers": headers})

    def test_signed_admin_cookie_is_accepted(self):
        signed_cookie = admin_auth.sign_admin_session(int(time.time()))
        request = self._request_with_cookie(f"{admin_auth.ADMIN_COOKIE}={signed_cookie}")

        self.assertTrue(admin_auth.is_admin_authenticated(request))

    def test_invalid_admin_cookie_is_rejected(self):
        request = self._request_with_cookie(f"{admin_auth.ADMIN_COOKIE}=admin:1:bad")

        self.assertFalse(admin_auth.is_admin_authenticated(request))

    def test_admin_api_key_allows_private_api_dependency(self):
        request = self._request_with_cookie()

        asyncio.run(admin_auth.require_admin_api_access(request, x_admin_api_key="test_api_key"))

    def test_admin_password_uses_helper(self):
        self.assertTrue(admin_auth.verify_admin_password("test_password"))
        self.assertFalse(admin_auth.verify_admin_password("wrong_password"))

    def test_missing_admin_auth_rejects_private_api_dependency(self):
        request = self._request_with_cookie()

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(admin_auth.require_admin_api_access(request, x_admin_api_key=None))

        self.assertEqual(ctx.exception.status_code, 401)


class DemoPageTests(unittest.TestCase):
    def _demo_file(self, directory: str) -> Path:
        path = Path(directory) / "index.html"
        path.write_text(
            '<script src="/static/tracker/tracker.js" data-site-id="PUT_SITE_ID_HERE"></script>',
            encoding="utf-8",
        )
        return path

    def test_demo_without_site_id_disables_tracker(self):
        with TemporaryDirectory() as tmpdir:
            html = render_demo_html(None, self._demo_file(tmpdir))

        self.assertIn('data-site-id=""', html)
        self.assertNotIn("PUT_SITE_ID_HERE", html)

    def test_demo_with_site_id_injects_tracker_site_id(self):
        with TemporaryDirectory() as tmpdir:
            html = render_demo_html("site_abc123", self._demo_file(tmpdir))

        self.assertIn('data-site-id="site_abc123"', html)
        self.assertNotIn("PUT_SITE_ID_HERE", html)

    def test_demo_rejects_invalid_site_id(self):
        with self.assertRaises(ValueError):
            validate_demo_site_id("<bad>")


class RouterProtectionTests(unittest.TestCase):
    def test_private_routers_are_registered_with_admin_dependency(self):
        router_source = Path("app/api/router.py").read_text(encoding="utf-8")
        private_router_names = [
            "clients_router",
            "sites_router",
            "knowledge_router",
            "classifications_router",
            "ai_reports_router",
            "site_status_router",
            "simple_analytics_router",
            "gsc_router",
            "site_score_router",
        ]

        for router_name in private_router_names:
            self.assertIn(
                f"api_router.include_router({router_name}, dependencies=private_dependencies)",
                router_source,
            )

        self.assertIn("api_router.include_router(events_router)", router_source)
        self.assertIn("api_router.include_router(page_snapshots_router)", router_source)
        self.assertIn("api_router.include_router(gsc_public_router)", router_source)
        self.assertIn("api_router.include_router(gsc_router, dependencies=private_dependencies)", router_source)

    def test_legacy_demo_site_is_not_mounted(self):
        main_source = Path("app/main.py").read_text(encoding="utf-8")

        self.assertNotIn('app.mount("/demo-site"', main_source)
        self.assertIn('@app.get("/demo"', main_source)


class GSCOAuthStateTests(unittest.TestCase):
    def setUp(self):
        self.original_password = settings.ADMIN_DASHBOARD_PASSWORD
        self.original_secret = settings.ADMIN_SESSION_SECRET
        settings.ADMIN_DASHBOARD_PASSWORD = "test_password"
        settings.ADMIN_SESSION_SECRET = "test_secret"

    def tearDown(self):
        settings.ADMIN_DASHBOARD_PASSWORD = self.original_password
        settings.ADMIN_SESSION_SECRET = self.original_secret

    def test_signed_oauth_state_roundtrip(self):
        state = gsc_oauth_service._sign_state("site_abc123")

        self.assertEqual(gsc_oauth_service._verify_state(state), "site_abc123")

    def test_tampered_oauth_state_is_rejected(self):
        state = gsc_oauth_service._sign_state("site_abc123")
        tampered = state.replace("site_abc123", "site_other")

        self.assertIsNone(gsc_oauth_service._verify_state(tampered))
