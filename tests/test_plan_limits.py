import unittest
from pathlib import Path

from app.services.plan_limits import get_plan_limits, normalize_account_plan, site_limit_message


class PlanLimitsTests(unittest.TestCase):
    def test_partner_is_default_account_plan(self):
        limits = get_plan_limits(None)

        self.assertEqual(limits.key, "partner")
        self.assertEqual(limits.max_sites, 3)
        self.assertTrue(limits.can_use_gsc)

    def test_unknown_plan_falls_back_to_partner(self):
        self.assertEqual(normalize_account_plan("unknown"), "partner")

    def test_site_limit_message_is_neutral(self):
        message = site_limit_message(get_plan_limits("start"))

        self.assertIn("текущего режима аккаунта", message)
        self.assertIn("свяжитесь с администратором сервиса", message)


class PlanMigrationTests(unittest.TestCase):
    def test_user_account_plan_migration_exists(self):
        migration_source = Path("migrations/versions/015_add_user_account_plan.py").read_text(encoding="utf-8")

        self.assertIn('"account_plan"', migration_source)
        self.assertIn('server_default="partner"', migration_source)
