import time
import unittest
import uuid
from pathlib import Path

from starlette.requests import Request

from app.core import user_auth
from app.core.config import settings


class UserAuthCookieTests(unittest.TestCase):
    def setUp(self):
        self.original_password = settings.ADMIN_DASHBOARD_PASSWORD
        self.original_secret = settings.ADMIN_SESSION_SECRET
        self.original_ttl = settings.ADMIN_SESSION_TTL_SECONDS
        settings.ADMIN_DASHBOARD_PASSWORD = "test_password"
        settings.ADMIN_SESSION_SECRET = "test_secret"
        settings.ADMIN_SESSION_TTL_SECONDS = 3600

    def tearDown(self):
        settings.ADMIN_DASHBOARD_PASSWORD = self.original_password
        settings.ADMIN_SESSION_SECRET = self.original_secret
        settings.ADMIN_SESSION_TTL_SECONDS = self.original_ttl

    def _request_with_cookie(self, cookie: str = "") -> Request:
        headers = []
        if cookie:
            headers.append((b"cookie", cookie.encode()))
        return Request({"type": "http", "headers": headers})

    def test_signed_user_cookie_returns_user_id(self):
        user_id = uuid.uuid4()
        signed_cookie = user_auth.sign_user_session(user_id, int(time.time()))

        self.assertEqual(user_auth.verify_user_session(signed_cookie), user_id)

    def test_invalid_user_cookie_is_rejected(self):
        self.assertIsNone(user_auth.verify_user_session("user:not-a-uuid:1:bad"))

    def test_expired_user_cookie_is_rejected(self):
        user_id = uuid.uuid4()
        signed_cookie = user_auth.sign_user_session(user_id, int(time.time()) - 7200)

        self.assertIsNone(user_auth.verify_user_session(signed_cookie))

    def test_request_cookie_returns_authenticated_user_id(self):
        user_id = uuid.uuid4()
        signed_cookie = user_auth.sign_user_session(user_id, int(time.time()))
        request = self._request_with_cookie(f"{user_auth.USER_COOKIE}={signed_cookie}")

        self.assertEqual(user_auth.get_authenticated_user_id(request), user_id)


class UserAuthRouteSourceTests(unittest.TestCase):
    def test_auth_router_is_registered(self):
        main_source = Path("app/main.py").read_text(encoding="utf-8")

        self.assertIn("from app.auth.routes import router as auth_router", main_source)
        self.assertIn("app.include_router(auth_router)", main_source)

    def test_root_redirects_to_user_auth_flow(self):
        admin_source = Path("app/admin/routes.py").read_text(encoding="utf-8")

        self.assertIn("get_authenticated_user_id(request)", admin_source)
        self.assertIn('headers={"Location": "/sites"}', admin_source)
        self.assertIn('headers={"Location": "/login"}', admin_source)

    def test_auth_routes_expose_registration_login_logout_and_sites(self):
        route_source = Path("app/auth/routes.py").read_text(encoding="utf-8")

        self.assertIn('@router.get("/register")', route_source)
        self.assertIn('@router.post("/register")', route_source)
        self.assertIn('@router.get("/login")', route_source)
        self.assertIn('@router.post("/login")', route_source)
        self.assertIn('@router.get("/logout")', route_source)
        self.assertIn('@router.get("/sites")', route_source)
        self.assertIn('@router.get("/sites/new")', route_source)
        self.assertIn('@router.post("/sites/new")', route_source)
        self.assertIn('@router.get("/sites/{site_id}/install")', route_source)
        self.assertIn('@router.get("/sites/{site_id}")', route_source)
        self.assertIn('@router.get("/sites/{site_id}/analytics/{metric}")', route_source)
        self.assertIn('@router.post("/sites/{site_id}/analysis/run")', route_source)
        self.assertIn("UserService(db)", route_source)
        self.assertIn("create_demo_site_for_user(db, user.id)", route_source)
        self.assertIn("UserSiteCreate(", route_source)
        self.assertIn("SiteService(db).list_sites_by_user(user_id)", route_source)
        self.assertIn("SiteService(db).create_site_for_user(user_id, site_data)", route_source)
        self.assertIn("ProductDashboardService(db).get_site_dashboard(site.site_id", route_source)
        self.assertIn("_build_analytics_detail(metric, dashboard", route_source)
        self.assertIn("background_tasks.add_task(run_site_analysis_task, site.site_id, 7)", route_source)
        self.assertIn('return _redirect(f"/sites/{site.site_id}/install")', route_source)
        self.assertIn("response.set_cookie(", route_source)
        self.assertIn('f"/sites/{demo_site.site_id}" if demo_site else "/sites"', route_source)

    def test_user_sites_template_uses_user_navigation(self):
        template_source = Path("app/templates/user_sites.html").read_text(encoding="utf-8")
        user_base_source = Path("app/templates/user_base.html").read_text(encoding="utf-8")

        self.assertIn('{% extends "user_base.html" %}', template_source)
        self.assertIn('href="/sites"', user_base_source)
        self.assertIn('href="/sites/new"', user_base_source)
        self.assertIn('href="/logout"', user_base_source)
        self.assertNotIn("/admin/logout", user_base_source)

    def test_user_site_form_template_exists(self):
        template_source = Path("app/templates/user_site_form.html").read_text(encoding="utf-8")

        self.assertIn('action="/sites/new"', template_source)
        self.assertIn('name="domain"', template_source)
        self.assertIn('name="allowed_domains"', template_source)
        self.assertIn('name="google_client_id"', template_source)
        self.assertIn('name="google_client_secret"', template_source)

    def test_user_site_install_template_exists(self):
        template_source = Path("app/templates/user_site_install.html").read_text(encoding="utf-8")

        self.assertIn("{{ site.site_id }}", template_source)
        self.assertIn("{{ install_code }}", template_source)
        self.assertIn("readonly", template_source)

    def test_user_site_dashboard_template_exists(self):
        template_source = Path("app/templates/user_site_dashboard.html").read_text(encoding="utf-8")
        sites_source = Path("app/templates/user_sites.html").read_text(encoding="utf-8")

        self.assertIn('{% extends "user_base.html" %}', template_source)
        self.assertIn("dashboard.tracker_analytics", template_source)
        self.assertIn("dashboard.latest_ai_report", template_source)
        self.assertIn("dashboard.tracker_analytics.realtime_search", template_source)
        self.assertIn('id="realtimeSearchChart"', template_source)
        self.assertIn("realtime-tabs", template_source)
        self.assertIn("Позиция", template_source)
        self.assertIn("data-chart-toggles", template_source)
        self.assertIn("metric-info-popover", template_source)
        self.assertIn("item.info", template_source)
        self.assertIn("row.ctr", template_source)
        self.assertIn("row.position", template_source)
        self.assertNotIn('id="gscChart"', template_source)
        self.assertNotIn("gsc-period-switcher", template_source)
        self.assertIn("dashboard.site_status.eta_label", template_source)
        self.assertIn('action="/sites/{{ site.site_id }}/analysis/run"', template_source)
        self.assertIn("metric-card-link", template_source)
        self.assertIn("/analytics/visitors", template_source)
        self.assertIn("/analytics/bots", template_source)
        self.assertIn('class="info-popover"', template_source)
        self.assertIn('aria-label="Информация о блоке"', template_source)
        self.assertIn('/demo?site_id={{ site.site_id }}', template_source)
        self.assertIn('href="/sites/{{ site.site_id }}"', sites_source)
        self.assertIn('/demo?site_id={{ site.site_id }}', sites_source)
        self.assertNotIn("/admin/sites/", sites_source)

    def test_user_base_loads_chart_script(self):
        base_source = Path("app/templates/user_base.html").read_text(encoding="utf-8")
        script_source = Path("app/static/js/charts.js").read_text(encoding="utf-8")

        self.assertIn('/static/js/charts.js', base_source)
        self.assertIn("initMetricCharts", script_source)
        self.assertIn("drawMetricChart", script_source)
        self.assertIn("initGscPeriodNavigation", script_source)
        self.assertIn("requestGscSection(url)", script_source)
        self.assertIn("XMLHttpRequest", script_source)
        self.assertIn("restoreGscScrollPosition", script_source)
        self.assertIn("sessionStorage.setItem('gscScrollY'", script_source)
        self.assertIn("replaceWith(nextSection)", script_source)

    def test_layouts_load_info_popover_script(self):
        user_base_source = Path("app/templates/user_base.html").read_text(encoding="utf-8")
        admin_base_source = Path("app/templates/base.html").read_text(encoding="utf-8")
        script_source = Path("app/static/js/ui.js").read_text(encoding="utf-8")

        self.assertIn('/static/js/ui.js', user_base_source)
        self.assertIn('/static/js/ui.js', admin_base_source)
        self.assertIn("initInfoPopovers", script_source)
        self.assertIn("mouseenter", script_source)
        self.assertIn("mouseleave", script_source)
        self.assertIn("mousemove", script_source)
        self.assertIn("touchstart", script_source)

    def test_demo_site_bootstrap_service_exists(self):
        service_source = Path("app/services/demo_site_bootstrap_service.py").read_text(encoding="utf-8")

        self.assertIn("create_demo_site_for_user", service_source)
        self.assertIn("seed_demo_site_data", service_source)
        self.assertIn("create_demo_gsc_data", service_source)
        self.assertIn("PageSpeedRepository", service_source)
        self.assertIn("is_bot=True", service_source)

    def test_info_popover_styles_exist(self):
        style_source = Path("app/static/css/style.css").read_text(encoding="utf-8")

        self.assertIn(".info-popover summary", style_source)
        self.assertIn(".info-popover div", style_source)
        self.assertIn(".status-card-actions", style_source)
        self.assertIn(".metric-card-link", style_source)

    def test_user_analytics_detail_template_exists(self):
        template_source = Path("app/templates/user_analytics_detail.html").read_text(encoding="utf-8")

        self.assertIn('{% extends "user_base.html" %}', template_source)
        self.assertIn("detail.summary", template_source)
        self.assertIn("detail.sections", template_source)
        self.assertIn("Назад к сайту", template_source)
