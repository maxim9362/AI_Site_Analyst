import unittest
from pathlib import Path

from pydantic import ValidationError

from app.core.password_hash import HASH_ALGORITHM, hash_password, verify_password
from app.core.config import settings
from app.schemas.site import SiteCreate, UserSiteCreate
from app.schemas.user import UserCreate
from app.services.site_service import SiteService


class PasswordHashTests(unittest.TestCase):
    def test_password_hash_roundtrip(self):
        password_hash = hash_password("password123")

        self.assertTrue(password_hash.startswith(f"{HASH_ALGORITHM}$"))
        self.assertTrue(verify_password("password123", password_hash))
        self.assertFalse(verify_password("wrong-password", password_hash))

    def test_password_hash_uses_random_salt(self):
        first_hash = hash_password("password123")
        second_hash = hash_password("password123")

        self.assertNotEqual(first_hash, second_hash)

    def test_invalid_password_hash_is_rejected(self):
        self.assertFalse(verify_password("password123", "not-a-valid-hash"))


class UserSchemaTests(unittest.TestCase):
    def test_user_create_normalizes_email(self):
        user = UserCreate(email="  USER@Example.COM  ", password="password123")

        self.assertEqual(user.email, "user@example.com")

    def test_user_create_rejects_short_password(self):
        with self.assertRaises(ValidationError):
            UserCreate(email="user@example.com", password="short")

    def test_user_create_rejects_invalid_email(self):
        with self.assertRaises(ValidationError):
            UserCreate(email="not-an-email", password="password123")

    def test_site_create_rejects_empty_domain(self):
        with self.assertRaises(ValidationError):
            SiteCreate(name="Example", domain="")

    def test_user_site_create_requires_google_credentials(self):
        site = UserSiteCreate(
            name="Example",
            domain="example.com",
            google_client_id="client-id",
            google_client_secret="client-secret",
        )

        self.assertEqual(site.google_client_id, "client-id")

        with self.assertRaises(ValidationError):
            UserSiteCreate(name="Example", domain="example.com", google_client_id="", google_client_secret="")


class SiteInstallCodeTests(unittest.TestCase):
    def setUp(self):
        self.original_app_base_url = settings.APP_BASE_URL
        settings.APP_BASE_URL = "https://app.example.com/"

    def tearDown(self):
        settings.APP_BASE_URL = self.original_app_base_url

    def test_tracker_install_code_uses_public_site_id_and_base_url(self):
        install_code = SiteService(None).build_tracker_install_code("site_abc123")

        self.assertEqual(
            install_code,
            '<script src="https://app.example.com/static/tracker/tracker.js" '
            'data-site-id="site_abc123" async></script>',
        )


class UserMigrationTests(unittest.TestCase):
    def test_users_migration_exists(self):
        migration_source = Path("migrations/versions/009_create_users.py").read_text(encoding="utf-8")

        self.assertIn('revision: str = "009"', migration_source)
        self.assertIn('op.create_table(', migration_source)
        self.assertIn('"users"', migration_source)
        self.assertIn('"password_hash"', migration_source)
        self.assertIn('op.create_index(op.f("ix_users_email")', migration_source)

    def test_site_user_owner_migration_exists(self):
        migration_source = Path("migrations/versions/010_add_site_user_owner.py").read_text(encoding="utf-8")

        self.assertIn('revision: str = "010"', migration_source)
        self.assertIn('down_revision: Union[str, None] = "009"', migration_source)
        self.assertIn('"sites"', migration_source)
        self.assertIn('"user_id"', migration_source)
        self.assertIn('"fk_sites_user_id_users"', migration_source)

    def test_site_google_credentials_migration_exists(self):
        migration_source = Path("migrations/versions/011_add_site_google_credentials.py").read_text(encoding="utf-8")

        self.assertIn('revision: str = "011"', migration_source)
        self.assertIn('down_revision: Union[str, None] = "010"', migration_source)
        self.assertIn('"google_client_id"', migration_source)
        self.assertIn('"google_client_secret"', migration_source)

    def test_site_status_includes_eta(self):
        source = Path("app/services/site_status_service.py").read_text(encoding="utf-8")

        self.assertIn("eta_label", source)
        self.assertIn("Примерно 1-3 минуты", source)
        self.assertIn("После первых визитов", source)

    def test_product_dashboard_builds_gsc_chart_data(self):
        source = Path("app/services/product_dashboard_service.py").read_text(encoding="utf-8")

        self.assertIn("gsc_chart_data", source)
        self.assertIn("def _build_gsc_chart_data", source)
        self.assertIn('"granularity": "hourly"', source)
        self.assertIn('"summary": [', source)
        self.assertIn('"key": "impressions"', source)
        self.assertIn('"key": "position"', source)
        self.assertIn("_merge_gsc_into_realtime_search", source)
        self.assertIn('"key": "google_clicks"', source)
        self.assertIn('"key": "google_position"', source)
        self.assertIn('"info": "Сколько переходов на сайт пришло из результатов поиска Google."', source)

    def test_traffic_sources_prioritize_utm_before_referrer(self):
        source = Path("app/services/simple_analytics_service.py").read_text(encoding="utf-8")

        self.assertIn("def _host_matches", source)
        self.assertLess(source.index("from_url = _detect_source_from_url"), source.index("from_ref = _detect_source_from_referrer"))
