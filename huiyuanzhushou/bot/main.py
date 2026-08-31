import logging
import math
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
CATALOG_API_URL = os.getenv(
    "CATALOG_API_URL",
    "https://huiyuanzhushou.vercel.app/api/catalog",
).rstrip("/")
BOT_DESCRIPTION = os.getenv(
    "BOT_DESCRIPTION",
    "一站式查询会员福利活动，支持按站点、金额、类型、分类和场馆筛选。",
).strip()
BOT_SHORT_DESCRIPTION = os.getenv(
    "BOT_SHORT_DESCRIPTION",
    "快速查询会员福利与预计彩金",
).strip()
WELCOME_IMAGE_URL = os.getenv("WELCOME_IMAGE_URL", "").strip()
WELCOME_TEXT = os.getenv("WELCOME_TEXT", "").strip()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("huiyuanzhushou-bot")

CATEGORIES = [
    ("all", "全站"),
    ("sports", "体育"),
    ("live", "真人"),
    ("esports", "电竞"),
    ("chess", "棋牌"),
    ("slots", "电子"),
    ("entertainment", "娱乐"),
    ("lottery", "彩票"),
]
CATEGORY_NAMES = dict(CATEGORIES)
QUICK_AMOUNTS = [100, 1_000, 10_000, 100_000]


async def sb_get(path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            },
            params=params,
        )
        response.raise_for_status()
        return response.json()


async def sb_post(path: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def get_sites() -> list[dict[str, Any]]:
    return await sb_get(
        "member_sites",
        {
            "select": "id,code,name",
            "is_enabled": "eq.true",
            "order": "sort_order.asc,name.asc",
        },
    )


async def fetch_catalog(params: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(CATALOG_API_URL, params=params)
        response.raise_for_status()
        return response.json()


async def get_accounts(telegram_id: int) -> list[dict[str, Any]]:
    channels = await sb_get(
        "member_contact_channels",
        {
            "select": "user_id,membership_id",
            "channel_type": "in.(telegram_bot,personal_telegram,main_bot,backup_bot)",
            "external_account_id": f"eq.{telegram_id}",
            "is_enabled": "eq.true",
            "limit": "1",
        },
    )
    if not channels:
        return []

    identity_filter: dict[str, str]
    if channels[0].get("membership_id"):
        identity_filter = {
            "membership_id": f"eq.{channels[0]['membership_id']}"
        }
    elif channels[0].get("user_id"):
        identity_filter = {"user_id": f"eq.{channels[0]['user_id']}"}
    else:
        return []

    accounts = await sb_get(
        "member_site_accounts",
        {
            "select": "id,site_id,account_name,vip_level,is_starred",
            **identity_filter,
            "is_enabled": "eq.true",
            "order": "is_starred.desc,updated_at.desc",
        },
    )
    site_map = {site["id"]: site for site in await get_sites()}
    return [
        {**account, "site": site_map[account["site_id"]]}
        for account in accounts
        if account.get("site_id") in site_map
    ]


async def ensure_telegram_membership(user: Any) -> str:
    rows = await sb_post(
        "rpc/get_or_create_telegram_membership",
        {
            "p_telegram_id": user.id,
            "p_display_name": user.full_name or f"Telegram {user.id}",
            "p_username": user.username,
        },
    )
    result: Any = rows[0] if isinstance(rows, list) and rows else rows
    membership_id = result.get("membership_id") if isinstance(result, dict) else result
    if not membership_id:
        raise RuntimeError("Telegram membership RPC returned no id")
    return str(membership_id)


async def add_site_account(user: Any, site_id: str, account_name: str) -> None:
    membership_id = await ensure_telegram_membership(user)
    existing = await sb_get(
        "member_site_accounts",
        {
            "select": "id",
            "membership_id": f"eq.{membership_id}",
            "site_id": f"eq.{site_id}",
            "account_name": f"eq.{account_name}",
            "is_enabled": "eq.true",
            "limit": "1",
        },
    )
    if existing:
        return
    await sb_post(
        "member_site_accounts",
        {
            "membership_id": membership_id,
            "site_id": site_id,
            "account_name": account_name,
            "metadata": {"source": "telegram_bot"},
        },
    )


def format_amount(value: float | int) -> str:
    number = float(value)
    if number.is_integer():
        return f"{number:,.0f}"
    return f"{number:,.2f}".rstrip("0").rstrip(".")


def selected_venue_names(data: dict[str, Any]) -> list[str]:
    selected = set(data.get("selected") or set())
    return [
        venue["name"]
        for venue in data.get("venues") or []
        if str(venue["code"]) in selected
    ]


def panel_text(data: dict[str, Any]) -> str:
    names = selected_venue_names(data)
    venue_text = "、".join(names) if names else "不限场馆"
    vip = f" · VIP{data['vip']}" if data.get("vip") is not None else ""
    prompt = ""
    if data.get("waiting_amount"):
        prompt = "\n\n✍️ 请直接在下方输入金额，例如：9000"

    return (
        "🔎 福利活动查询\n\n"
        f"👤 账户：{data.get('account') or '临时查询'}{vip}\n"
        f"🏢 站点：{data.get('site_name', '请选择')}\n"
        f"💰 金额：{format_amount(data.get('amount', 1_000))}\n"
        f"💳 类型：{'充值' if data.get('basis') == 'deposit' else '投注'}\n"
        f"🎮 分类：{CATEGORY_NAMES.get(data.get('category', 'all'), '全站')}\n"
        f"🏟 场馆：{venue_text}\n\n"
        "修改条件后，直接点击查询。"
        f"{prompt}"
    )


def option_button(
    label: str,
    callback_data: str,
    *,
    selected: bool = False,
    style: str | None = None,
) -> InlineKeyboardButton:
    if selected and not label.startswith("🔵 ✓ "):
        label = f"🔵 ✓ {label}"
    return InlineKeyboardButton(
        label,
        callback_data=callback_data,
        style=style or ("primary" if selected else None),
    )


def main_panel(data: dict[str, Any]) -> InlineKeyboardMarkup:
    amount = float(data.get("amount", 1_000))
    amount_mode = data.get("amount_mode", "quick")
    basis = data.get("basis", "bet")
    category = data.get("category", "all")
    selected = set(data.get("selected") or set())

    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton("👤 会员账户 / 站点", callback_data="source")],
        [
            option_button(
                format_amount(value),
                f"a:{value}",
                selected=amount_mode == "quick" and amount == value,
            )
            for value in QUICK_AMOUNTS
        ],
    ]

    custom_label = "✏️ 自定义金额"
    if amount_mode == "custom":
        custom_label = f"✏️ 自定义金额：{format_amount(amount)}"
    rows.append(
        [
            option_button(
                custom_label,
                "custom",
                selected=amount_mode == "custom",
            )
        ]
    )
    rows.append(
        [
            option_button("投注", "b:bet", selected=basis == "bet"),
            option_button("充值", "b:deposit", selected=basis == "deposit"),
        ]
    )

    for index in range(0, len(CATEGORIES), 4):
        rows.append(
            [
                option_button(name, f"c:{value}", selected=category == value)
                for value, name in CATEGORIES[index:index + 4]
            ]
        )

    venue_label = (
        f"🏟 场馆（已选 {len(selected)} 个）"
        if selected
        else "🏟 选择场馆（不限）"
    )
    rows.extend(
        [
            [option_button(venue_label, "venues", selected=bool(selected))],
            [InlineKeyboardButton("🔍 查询符合活动", callback_data="go")],
        ]
    )
    return InlineKeyboardMarkup(rows)


def source_keyboard(data: dict[str, Any]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    current_account_id = data.get("account_id")

    for account in (data.get("accounts") or {}).values():
        star = "⭐ " if account.get("is_starred") else ""
        vip = account.get("vip_level")
        vip_text = f"VIP{vip}" if vip is not None else "VIP未设置"
        rows.append(
            [
                option_button(
                    f"{star}{account['site']['name']} · "
                    f"{account.get('account_name') or '会员'} · {vip_text}",
                    f"acct:{account['id']}",
                    selected=current_account_id == account["id"],
                )
            ]
        )

    for site in (data.get("sites") or {}).values():
        rows.append(
            [
                option_button(
                    f"临时 · {site['name']}",
                    f"site:{site['id']}",
                    selected=(
                        current_account_id is None
                        and data.get("site_id") == site["id"]
                    ),
                )
            ]
        )

    rows.append([InlineKeyboardButton("➕ 添加会员账户", callback_data="addacct")])
    rows.append([InlineKeyboardButton("⬅️ 返回", callback_data="panel")])
    return InlineKeyboardMarkup(rows)


def add_account_site_keyboard(data: dict[str, Any]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(site["name"], callback_data=f"addsite:{site['id']}")]
        for site in (data.get("sites") or {}).values()
    ]
    rows.append([InlineKeyboardButton("⬅️ 返回账户列表", callback_data="source")])
    return InlineKeyboardMarkup(rows)


def venue_panel_text(data: dict[str, Any]) -> str:
    venues = data.get("venues") or []
    selected = set(data.get("selected") or set())
    if not selected:
        status = "当前：不限场馆"
    else:
        status = f"当前已选 {len(selected)} / {len(venues)} 个场馆"
    return (
        "🏟 选择场馆（支持多选）\n\n"
        f"{status}\n"
        "点击场馆可选中，再次点击可取消。"
    )


def venue_keyboard(data: dict[str, Any]) -> InlineKeyboardMarkup:
    venues = data.get("venues") or []
    selected = set(data.get("selected") or set())
    all_codes = {str(venue["code"]) for venue in venues}
    rows: list[list[InlineKeyboardButton]] = [
        [
            option_button("不限场馆", "vnone", selected=not selected),
            option_button(
                "全选",
                "vall",
                selected=bool(all_codes) and selected == all_codes,
            ),
        ]
    ]

    for index in range(0, len(venues), 2):
        row: list[InlineKeyboardButton] = []
        for venue in venues[index:index + 2]:
            code = str(venue["code"])
            row.append(
                option_button(
                    venue["name"],
                    f"v:{code}",
                    selected=code in selected,
                )
            )
        rows.append(row)

    rows.append([InlineKeyboardButton("✅ 完成", callback_data="panel")])
    return InlineKeyboardMarkup(rows)


def toggle_venue(data: dict[str, Any], code: str) -> None:
    selected = set(data.get("selected") or set())
    if code in selected:
        selected.remove(code)
    else:
        selected.add(code)
    data["selected"] = selected


def build_query_params(data: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {
        "site_id": data["site_id"],
        "amount": data["amount"],
        "amount_basis": data.get("basis", "bet"),
        "category": data.get("category", "all"),
    }
    if data.get("vip") is not None:
        params["vip"] = data["vip"]
    selected = sorted(set(data.get("selected") or set()))
    if selected:
        params["venues"] = ",".join(selected)
    return params


async def load_venues(data: dict[str, Any]) -> None:
    result = await fetch_catalog(
        {
            "site_id": data["site_id"],
            "category": data.get("category", "all"),
            "meta": 1,
        }
    )
    data["venues"] = result.get("venues") or []
    data["selected"] = set()


def remember_panel(data: dict[str, Any], message: Any) -> None:
    data["panel_chat_id"] = message.chat_id
    data["panel_message_id"] = message.message_id


async def delete_message_safely(bot: Any, chat_id: int, message_id: int | None) -> None:
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramError:
        log.debug("Could not delete message %s", message_id, exc_info=True)


async def clear_amount_prompt(
    context: ContextTypes.DEFAULT_TYPE,
    data: dict[str, Any],
) -> None:
    chat_id = data.get("panel_chat_id")
    prompt_id = data.pop("amount_prompt_message_id", None)
    data["waiting_amount"] = False
    if chat_id and prompt_id:
        await delete_message_safely(context.bot, chat_id, prompt_id)


async def clear_account_prompt(
    context: ContextTypes.DEFAULT_TYPE,
    data: dict[str, Any],
) -> None:
    chat_id = data.get("panel_chat_id")
    prompt_id = data.pop("account_prompt_message_id", None)
    data["waiting_account_name"] = False
    data.pop("add_site_id", None)
    if chat_id and prompt_id:
        await delete_message_safely(context.bot, chat_id, prompt_id)


async def edit_query_message(
    query: Any,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except BadRequest as error:
        if "Message is not modified" not in str(error):
            raise


async def show_main_panel(query: Any, data: dict[str, Any]) -> None:
    data["waiting_amount"] = False
    await edit_query_message(query, panel_text(data), main_panel(data))
    if query.message:
        remember_panel(data, query.message)


async def show_venue_panel(query: Any, data: dict[str, Any]) -> None:
    await edit_query_message(
        query,
        venue_panel_text(data),
        venue_keyboard(data),
    )
    if query.message:
        remember_panel(data, query.message)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    if WELCOME_IMAGE_URL:
        try:
            await message.reply_photo(
                photo=WELCOME_IMAGE_URL,
                caption=WELCOME_TEXT or None,
            )
        except TelegramError:
            log.exception("Failed to send configured welcome image")

    try:
        sites = await get_sites()
        accounts = await get_accounts(user.id)
    except Exception:
        log.exception("Failed to load sites or member accounts")
        await message.reply_text("读取会员资料失败，请稍后再试。")
        return

    data = context.user_data
    data.update(
        {
            "sites": {site["id"]: site for site in sites},
            "accounts": {account["id"]: account for account in accounts},
            "amount": 1_000.0,
            "amount_mode": "quick",
            "basis": "bet",
            "category": "all",
            "vip": None,
            "selected": set(),
            "waiting_amount": False,
            "waiting_account_name": False,
        }
    )

    if accounts:
        account = accounts[0]
        data.update(
            {
                "account_id": account["id"],
                "site_id": account["site_id"],
                "site_name": account["site"]["name"],
                "account": account.get("account_name"),
                "vip": account.get("vip_level"),
            }
        )
    elif sites:
        site = sites[0]
        data.update(
            {
                "account_id": None,
                "site_id": site["id"],
                "site_name": site["name"],
                "account": None,
            }
        )
    else:
        await message.reply_text("目前还没有启用的站点。")
        return

    try:
        await load_venues(data)
    except Exception:
        log.exception("Failed to load venues during start")
        data["venues"] = []
        data["selected"] = set()

    sent = await message.reply_text(panel_text(data), reply_markup=main_panel(data))
    remember_panel(data, sent)


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return

    await query.answer()
    action = query.data or ""
    data = context.user_data
    remember_panel(data, query.message)

    try:
        if action != "custom" and data.get("waiting_amount"):
            await clear_amount_prompt(context, data)
        if not action.startswith("addsite:") and data.get("waiting_account_name"):
            await clear_account_prompt(context, data)

        if action == "panel":
            await show_main_panel(query, data)
            return

        if action == "source":
            await query.edit_message_text(
                "选择会员账户或临时站点：",
                reply_markup=source_keyboard(data),
            )
            return

        if action == "addacct":
            await query.edit_message_text(
                "➕ 添加会员账户\n\n先选择账户所属站点：",
                reply_markup=add_account_site_keyboard(data),
            )
            return

        if action.startswith("addsite:"):
            site = (data.get("sites") or {}).get(action[8:])
            if not site:
                await query.edit_message_text("站点已失效，请发送 /start 重新读取。")
                return
            data["add_site_id"] = site["id"]
            data["waiting_account_name"] = True
            await query.edit_message_text(
                f"➕ 添加会员账户\n\n站点：{site['name']}\n请直接在下方输入会员账户名。",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("取消", callback_data="source")]]
                ),
            )
            prompt = await query.message.reply_text(
                "请输入会员账户名",
                reply_markup=ForceReply(
                    selective=True,
                    input_field_placeholder="会员账户名",
                ),
            )
            data["account_prompt_message_id"] = prompt.message_id
            return

        if action.startswith("acct:"):
            account = (data.get("accounts") or {}).get(action[5:])
            if not account:
                await query.edit_message_text("会员账户已失效，请发送 /start 重新读取。")
                return
            data.update(
                {
                    "account_id": account["id"],
                    "site_id": account["site_id"],
                    "site_name": account["site"]["name"],
                    "account": account.get("account_name"),
                    "vip": account.get("vip_level"),
                }
            )
            await load_venues(data)
            await show_main_panel(query, data)
            return

        if action.startswith("site:"):
            site = (data.get("sites") or {}).get(action[5:])
            if not site:
                await query.edit_message_text("站点已失效，请发送 /start 重新读取。")
                return
            data.update(
                {
                    "account_id": None,
                    "site_id": site["id"],
                    "site_name": site["name"],
                    "account": None,
                    "vip": None,
                }
            )
            await load_venues(data)
            await show_main_panel(query, data)
            return

        if action.startswith("a:"):
            data["amount"] = float(action[2:])
            data["amount_mode"] = "quick"
            await show_main_panel(query, data)
            return

        if action == "custom":
            await clear_amount_prompt(context, data)
            data["waiting_amount"] = True
            await edit_query_message(
                query,
                panel_text(data),
                main_panel(data),
            )
            prompt = await query.message.reply_text(
                "✍️ 请输入自定义金额，例如：9000",
                reply_markup=ForceReply(
                    selective=True,
                    input_field_placeholder="请输入金额",
                ),
            )
            data["amount_prompt_message_id"] = prompt.message_id
            return

        if action.startswith("b:"):
            data["basis"] = action[2:]
            await show_main_panel(query, data)
            return

        if action.startswith("c:"):
            next_category = action[2:]
            if next_category != data.get("category"):
                data["category"] = next_category
                await load_venues(data)
            await show_main_panel(query, data)
            return

        if action == "venues":
            await show_venue_panel(query, data)
            return

        if action == "vall":
            data["selected"] = {
                str(venue["code"]) for venue in data.get("venues") or []
            }
            await show_venue_panel(query, data)
            return

        if action == "vnone":
            data["selected"] = set()
            await show_venue_panel(query, data)
            return

        if action.startswith("v:"):
            toggle_venue(data, action[2:])
            await show_venue_panel(query, data)
            return

        if action == "go":
            await run_query(query, data)
    except Exception:
        log.exception("Callback failed: %s", action)
        await query.edit_message_text(
            "操作失败，请稍后重试。",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ 返回查询面板", callback_data="panel")]]
            ),
        )


async def text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.user_data
    message = update.effective_message
    if not message or not message.text:
        return

    if data.get("waiting_account_name"):
        await save_account_name(update, context)
        return

    if not data.get("waiting_amount"):
        return

    raw_value = message.text.replace(",", "").strip()
    try:
        amount = float(raw_value)
        if amount <= 0 or not math.isfinite(amount):
            raise ValueError
    except ValueError:
        chat_id = data.get("panel_chat_id") or message.chat_id
        old_prompt_id = data.pop("amount_prompt_message_id", None)
        await delete_message_safely(context.bot, chat_id, old_prompt_id)
        await delete_message_safely(context.bot, chat_id, message.message_id)
        prompt = await context.bot.send_message(
            chat_id=chat_id,
            text="金额格式不正确，请输入大于 0 的数字，例如：9000",
            reply_markup=ForceReply(
                selective=True,
                input_field_placeholder="请输入金额",
            ),
        )
        data["amount_prompt_message_id"] = prompt.message_id
        return

    data["amount"] = amount
    data["amount_mode"] = "custom"
    data["waiting_amount"] = False

    chat_id = data.get("panel_chat_id") or message.chat_id
    panel_message_id = data.get("panel_message_id")
    panel_updated = False
    if panel_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=panel_message_id,
                text=panel_text(data),
                reply_markup=main_panel(data),
            )
            panel_updated = True
        except BadRequest as error:
            if "Message is not modified" in str(error):
                panel_updated = True
            else:
                log.warning("Could not update stored query panel: %s", error)

    if not panel_updated:
        sent = await message.reply_text(panel_text(data), reply_markup=main_panel(data))
        remember_panel(data, sent)

    prompt_id = data.pop("amount_prompt_message_id", None)
    await delete_message_safely(context.bot, chat_id, prompt_id)
    await delete_message_safely(context.bot, chat_id, message.message_id)


async def save_account_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.user_data
    user = update.effective_user
    message = update.effective_message
    if not user or not message or not message.text:
        return

    account_name = " ".join(message.text.split())
    site_id = data.get("add_site_id")
    site = (data.get("sites") or {}).get(site_id)
    if not site:
        await message.reply_text("站点已失效，请发送 /start 后重试。")
        await clear_account_prompt(context, data)
        return
    if not 2 <= len(account_name) <= 64:
        await message.reply_text("账户名需要 2–64 个字符，请重新输入。")
        return

    try:
        await add_site_account(user, site_id, account_name)
        accounts = await get_accounts(user.id)
    except Exception:
        log.exception("Failed to add member site account")
        await message.reply_text("保存账户失败，请稍后重试。")
        return

    data["accounts"] = {account["id"]: account for account in accounts}
    account = next(
        (
            item
            for item in accounts
            if item["site_id"] == site_id and item["account_name"] == account_name
        ),
        None,
    )
    if account:
        data.update(
            {
                "account_id": account["id"],
                "site_id": account["site_id"],
                "site_name": account["site"]["name"],
                "account": account["account_name"],
                "vip": account.get("vip_level"),
            }
        )
        await load_venues(data)

    chat_id = data.get("panel_chat_id") or message.chat_id
    prompt_id = data.pop("account_prompt_message_id", None)
    data["waiting_account_name"] = False
    data.pop("add_site_id", None)
    await delete_message_safely(context.bot, chat_id, prompt_id)
    await delete_message_safely(context.bot, chat_id, message.message_id)
    panel_message_id = data.get("panel_message_id")
    if panel_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=panel_message_id,
                text=f"✅ 已添加：{site['name']} · {account_name}\n\n{panel_text(data)}",
                reply_markup=main_panel(data),
            )
            return
        except TelegramError:
            log.warning("Could not update account panel", exc_info=True)

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ 已添加：{site['name']} · {account_name}\n\n{panel_text(data)}",
        reply_markup=main_panel(data),
    )
    remember_panel(data, sent)


async def run_query(query: Any, data: dict[str, Any]) -> None:
    params = build_query_params(data)
    await query.edit_message_text("正在查询活动…")

    try:
        result = await fetch_catalog(params)
        promotions = result.get("promotions") or []
    except Exception:
        log.exception("Catalog query failed")
        await query.edit_message_text(
            "查询失败，请稍后重试。",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ 返回查询面板", callback_data="panel")]]
            ),
        )
        return

    if not promotions:
        output = "没有找到符合当前条件的活动。"
    else:
        blocks: list[str] = []
        for index, promotion in enumerate(promotions[:10], 1):
            estimated = promotion.get("estimated_bonus")
            estimated_text = (
                format_amount(float(estimated)) if estimated is not None else "待规则确认"
            )
            block = f"{index}. {promotion.get('title', '未命名活动')}\n预计彩金：{estimated_text}"
            if promotion.get("summary"):
                block += f"\n{promotion['summary']}"
            blocks.append(block)
        output = "\n\n".join(blocks)
        if len(promotions) > 10:
            output += f"\n\n另有 {len(promotions) - 10} 个活动未展开。"

    await query.edit_message_text(
        output[:3900],
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ 返回查询面板", callback_data="panel")]]
        ),
    )


async def setup_bot(application: Application) -> None:
    if BOT_DESCRIPTION:
        await application.bot.set_my_description(BOT_DESCRIPTION[:512])
    if BOT_SHORT_DESCRIPTION:
        await application.bot.set_my_short_description(BOT_SHORT_DESCRIPTION[:120])


def main() -> None:
    application = Application.builder().token(TOKEN).post_init(setup_bot).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_input)
    )
    log.info("Bot started with long polling")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
