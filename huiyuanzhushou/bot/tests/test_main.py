import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402


def button_by_callback(markup, callback_data):
    for row in markup.inline_keyboard:
        for button in row:
            if button.callback_data == callback_data:
                return button
    raise AssertionError(f"Button not found: {callback_data}")


class QueryPanelTests(unittest.TestCase):
    def base_data(self):
        return {
            "site_id": "site-1",
            "site_name": "星空",
            "amount": 1_000.0,
            "amount_mode": "quick",
            "basis": "deposit",
            "category": "slots",
            "vip": None,
            "venues": [
                {"code": "PG", "name": "PG电子"},
                {"code": "JDB", "name": "JDB电子"},
                {"code": "CQ9", "name": "CQ9电子"},
            ],
            "selected": {"PG", "JDB"},
        }

    def test_selected_main_options_use_primary_style(self):
        markup = main.main_panel(self.base_data())
        self.assertEqual(button_by_callback(markup, "a:1000").style, "primary")
        self.assertEqual(button_by_callback(markup, "b:deposit").style, "primary")
        self.assertEqual(button_by_callback(markup, "c:slots").style, "primary")
        self.assertIsNone(button_by_callback(markup, "b:bet").style)

    def test_custom_amount_is_shown_and_selected(self):
        data = self.base_data()
        data.update({"amount": 9_000.0, "amount_mode": "custom"})
        button = button_by_callback(main.main_panel(data), "custom")
        self.assertEqual(button.style, "primary")
        self.assertIn("9,000", button.text)

    def test_multiple_venues_stay_selected(self):
        data = self.base_data()
        markup = main.venue_keyboard(data)
        self.assertEqual(button_by_callback(markup, "v:PG").style, "primary")
        self.assertEqual(button_by_callback(markup, "v:JDB").style, "primary")
        self.assertIsNone(button_by_callback(markup, "v:CQ9").style)

        main.toggle_venue(data, "CQ9")
        self.assertEqual(data["selected"], {"PG", "JDB", "CQ9"})
        main.toggle_venue(data, "PG")
        self.assertEqual(data["selected"], {"JDB", "CQ9"})

    def test_unlimited_venue_is_selected_when_empty(self):
        data = self.base_data()
        data["selected"] = set()
        markup = main.venue_keyboard(data)
        self.assertEqual(button_by_callback(markup, "vnone").style, "primary")

    def test_query_contains_all_selected_venues(self):
        params = main.build_query_params(self.base_data())
        self.assertEqual(params["venues"], "JDB,PG")


if __name__ == "__main__":
    unittest.main()
