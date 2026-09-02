import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

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


def callback_row(markup, callback_data):
    for row in markup.inline_keyboard:
        if any(button.callback_data == callback_data for button in row):
            return [button.callback_data for button in row]
    raise AssertionError(f"Button row not found: {callback_data}")


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

    def test_deposit_is_before_bet(self):
        markup = main.main_panel(self.base_data())
        self.assertEqual(
            callback_row(markup, "b:deposit"),
            ["b:deposit", "b:bet"],
        )

    def test_bot_command_menu_contains_confirmed_commands(self):
        self.assertEqual(
            [command.command for command in main.BOT_COMMANDS],
            ["start", "account", "close", "help"],
        )

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
        self.assertEqual(callback_row(markup, "close"), ["close", "go"])

    def test_close_button_is_first_in_secondary_panels(self):
        data = self.base_data()
        data.update({"accounts": {}, "sites": {}})
        self.assertEqual(
            callback_row(main.source_keyboard(data), "close"),
            ["close", "panel"],
        )
        self.assertEqual(
            callback_row(main.add_account_site_keyboard(data), "close"),
            ["close", "source"],
        )
        self.assertEqual(
            callback_row(main.venue_keyboard(data), "close"),
            ["close", "panel"],
        )

    def test_add_account_site_picker_lists_every_site(self):
        data = self.base_data()
        data["sites"] = {
            "site-1": {"id": "site-1", "name": "星空"},
            "site-2": {"id": "site-2", "name": "银河"},
        }
        markup = main.add_account_site_keyboard(data)
        self.assertEqual(button_by_callback(markup, "addsite:site-1").text, "星空")
        self.assertEqual(button_by_callback(markup, "addsite:site-2").text, "银河")


class CommandBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_reset_closes_existing_panel(self):
        bot = SimpleNamespace(edit_message_text=AsyncMock(), delete_message=AsyncMock())
        context = SimpleNamespace(
            bot=bot,
            user_data={
                "panel_chat_id": 123,
                "panel_message_id": 456,
                "amount_prompt_message_id": None,
                "account_prompt_message_id": None,
            },
        )

        await main.reset_existing_query(context)

        bot.edit_message_text.assert_awaited_once_with(
            chat_id=123,
            message_id=456,
            text="♻️ 原查询面板已关闭，请使用下方的新面板。",
            reply_markup=None,
        )
        self.assertEqual(context.user_data, {})

    async def test_group_command_redirects_to_private_chat(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(type="group"),
            effective_message=message,
        )
        context = SimpleNamespace(
            bot=SimpleNamespace(username="member_helper_bot"),
        )

        allowed = await main.require_private_chat(update, context)

        self.assertFalse(allowed)
        message.reply_text.assert_awaited_once()
        reply_markup = message.reply_text.await_args.kwargs["reply_markup"]
        self.assertEqual(
            reply_markup.inline_keyboard[0][0].url,
            "https://t.me/member_helper_bot?start=group",
        )


if __name__ == "__main__":
    unittest.main()
