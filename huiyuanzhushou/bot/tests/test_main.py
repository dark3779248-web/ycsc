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
            ["start"],
        )

    def test_persistent_shortcut_keyboard_has_two_rows(self):
        markup = main.shortcut_keyboard()
        self.assertTrue(markup.is_persistent)
        self.assertTrue(markup.resize_keyboard)
        self.assertEqual(
            [[button.text for button in row] for row in markup.keyboard],
            [
                ["🔍 查询活动", "👤 会员账户", "➕ 添加账户"],
                ["⚙️ 管理账户", "✖️ 关闭查询", "❓ 使用帮助"],
            ],
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

    def test_account_picker_contains_management_entry_when_accounts_exist(self):
        data = self.base_data()
        data.update(
            {
                "accounts": {
                    "account-1": {
                        "id": "account-1",
                        "site_id": "site-1",
                        "site": {"id": "site-1", "name": "星空"},
                        "account_name": "test001",
                        "vip_level": 8,
                    }
                },
                "sites": {},
                "account_id": "account-1",
            }
        )
        markup = main.source_keyboard(data)
        self.assertEqual(
            button_by_callback(markup, "manageaccts").text,
            "⚙️ 修改 / 删除账户",
        )
        self.assertEqual(
            button_by_callback(markup, "renameacct:account-1").text,
            "✏️ 修改名称",
        )
        self.assertEqual(
            button_by_callback(markup, "changevip:account-1").text,
            "🎖 修改 VIP",
        )
        self.assertEqual(
            button_by_callback(markup, "deleteacct:account-1").text,
            "🗑 删除账户",
        )

    def test_every_account_has_its_own_action_buttons(self):
        data = self.base_data()
        data.update(
            {
                "account_id": "account-1",
                "accounts": {
                    account_id: {
                        "id": account_id,
                        "site_id": "site-1",
                        "site": {"id": "site-1", "name": "星空"},
                        "account_name": account_name,
                        "vip_level": vip,
                    }
                    for account_id, account_name, vip in (
                        ("account-1", "test001", 8),
                        ("account-2", "test002", 0),
                    )
                },
                "sites": {},
            }
        )
        markup = main.source_keyboard(data)
        for account_id in ("account-1", "account-2"):
            self.assertEqual(
                button_by_callback(markup, f"renameacct:{account_id}").text,
                "✏️ 修改名称",
            )
            self.assertEqual(
                button_by_callback(markup, f"changevip:{account_id}").text,
                "🎖 修改 VIP",
            )
            self.assertEqual(
                button_by_callback(markup, f"deleteacct:{account_id}").text,
                "🗑 删除账户",
            )

    def test_account_management_has_all_edit_and_delete_actions(self):
        account = {
            "id": "account-1",
            "site_id": "site-1",
            "site": {"id": "site-1", "name": "星空"},
            "account_name": "test001",
            "vip_level": 8,
        }
        markup = main.manage_account_keyboard(account)
        self.assertEqual(
            button_by_callback(markup, "renameacct:account-1").text,
            "✏️ 修改账户名",
        )
        self.assertEqual(
            button_by_callback(markup, "changesite:account-1").text,
            "🏢 修改站点",
        )
        self.assertEqual(
            button_by_callback(markup, "changevip:account-1").text,
            "🎖 修改 VIP",
        )
        self.assertEqual(
            button_by_callback(markup, "deleteacct:account-1").text,
            "🗑 删除账户",
        )
        self.assertEqual(callback_row(markup, "close"), ["close", "manageaccts"])

    def test_vip_parser_accepts_only_zero_to_ninety_nine(self):
        self.assertEqual(main.parse_vip_level("0"), 0)
        self.assertEqual(main.parse_vip_level(" 8 "), 8)
        self.assertEqual(main.parse_vip_level("99"), 99)
        self.assertIsNone(main.parse_vip_level("-1"))
        self.assertIsNone(main.parse_vip_level("100"))
        self.assertIsNone(main.parse_vip_level("VIP8"))

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
    async def test_venue_cache_avoids_repeated_catalog_requests(self):
        data = {
            "site_id": "site-1",
            "category": "all",
            "venue_cache": {},
            "selected": set(),
        }
        original = main.fetch_site_venues
        main.fetch_site_venues = AsyncMock(
            return_value=[{"code": "PG", "name": "PG电子"}]
        )
        try:
            await main.load_venues(data)
            await main.load_venues(data)
        finally:
            mocked_fetch = main.fetch_site_venues
            main.fetch_site_venues = original

        mocked_fetch.assert_awaited_once_with("site-1", "all")
        self.assertTrue(main.venues_are_cached(data))

    async def test_account_update_targets_only_active_exact_id(self):
        original = main.sb_patch
        main.sb_patch = AsyncMock(return_value=[{"id": "account-1"}])
        try:
            await main.update_site_account("account-1", {"vip_level": 9})
        finally:
            mocked_patch = main.sb_patch
            main.sb_patch = original

        mocked_patch.assert_awaited_once()
        path, params, payload = mocked_patch.await_args.args
        self.assertEqual(path, "member_site_accounts")
        self.assertEqual(
            params,
            {"id": "eq.account-1", "is_enabled": "eq.true"},
        )
        self.assertEqual(payload["vip_level"], 9)
        self.assertIn("updated_at", payload)

    async def test_new_account_is_saved_with_vip(self):
        original_ensure = main.ensure_telegram_membership
        original_get = main.sb_get
        original_post = main.sb_post
        main.ensure_telegram_membership = AsyncMock(return_value="membership-1")
        main.sb_get = AsyncMock(return_value=[])
        main.sb_post = AsyncMock(return_value=[{"id": "account-1"}])
        try:
            await main.add_site_account(
                SimpleNamespace(id=123), "site-1", "test001", 8
            )
        finally:
            mocked_post = main.sb_post
            main.ensure_telegram_membership = original_ensure
            main.sb_get = original_get
            main.sb_post = original_post

        payload = mocked_post.await_args.args[1]
        self.assertEqual(payload["vip_level"], 8)

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
