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
        selected_amount = button_by_callback(markup, "a:1000")
        self.assertEqual(selected_amount.style, "primary")
        self.assertTrue(selected_amount.text.startswith("🔵 ✓ "))
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

    def test_venue_picker_identifies_selected_site(self):
        text = main.venue_panel_text(self.base_data())
        self.assertIn("🏟 星空 · 选择场馆", text)

    def test_unlimited_venue_is_selected_when_empty(self):
        data = self.base_data()
        data["selected"] = set()
        markup = main.venue_keyboard(data)
        self.assertEqual(button_by_callback(markup, "vnone").style, "primary")

    def test_query_contains_all_selected_venues(self):
        params = main.build_query_params(self.base_data())
        self.assertEqual(params["venues"], "JDB,PG")

    def test_account_picker_contains_add_account(self):
        data = self.base_data()
        data.update({"accounts": {}, "sites": {}})
        markup = main.source_keyboard(data)
        self.assertEqual(
            button_by_callback(markup, "addacct").text,
            "➕ 添加会员账户",
        )
        self.assertEqual(button_by_callback(markup, "close").text, "✖️ 关闭")

    def test_main_panel_contains_close_button(self):
        markup = main.main_panel(self.base_data())
        self.assertEqual(button_by_callback(markup, "close").text, "✖️ 关闭查询")

    def test_add_account_site_picker_lists_every_site(self):
        data = self.base_data()
        data["sites"] = {
            "site-1": {"id": "site-1", "name": "星空"},
            "site-2": {"id": "site-2", "name": "银河"},
        }
        markup = main.add_account_site_keyboard(data)
        self.assertEqual(button_by_callback(markup, "addsite:site-1").text, "星空")
        self.assertEqual(button_by_callback(markup, "addsite:site-2").text, "银河")


if __name__ == "__main__":
    unittest.main()
