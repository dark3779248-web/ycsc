import logging
import os
from typing import Any
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
CATALOG_API_URL = os.getenv(
    "CATALOG_API_URL",
    "https://huiyuanzhushou.vercel.app/api/catalog",
).rstrip("/")

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
QUICK_AMOUNTS = [100, 1000, 10000, 100000]


def sb_headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }


async def sb_get(path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers=sb_headers(),
            params=params,
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


async def get_member_accounts(telegram_id: int) -> list[dict[str, Any]]:
    channels = await sb_get(
        "member_contact_channels",
        {
            "select": "user_id",
            "channel_type": "eq.telegram",
            "external_account_id": f"eq.{telegram_id}",
            "is_enabled": "eq.true",
            "limit": "1",
        },
    )
    if not channels or not channels[0].get("user_id"):
        return []

    user_id = channels[0]["user_id"]
    accounts = await sb_get(
        "member_site_accounts",
        {
            "select": "id,site_id,account_name,vip_level,is_starred",
            "user_id": f"eq.{user_id}",
            "is_enabled": "eq.true",
            "order": "is_starred.desc,updated_at.desc",
        },
    )
    if not accounts:
        return []

    sites = await get_sites()
    site_map = {site["id"]: site for site in sites}
    result: list[dict[str, Any]] = []
    for account in accounts:
        site = site_map.get(account.get("site_id"))
        if not site:
            continue
        result.append({**account, "site": site})
    return result


async def fetch_catalog(params: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(CATALOG_API_URL, params=params)
        response.raise_for_status()
        return response.json()


def reset_flow(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()


def account_keyboard(accounts: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for account in accounts:
        site = account["site"]
        vip = account.get("vip_level")
        account_name = account.get("account_name") or "会员账户"
        star = "⭐ " if account.get("is_starred") else ""
        vip_text = f"VIP{vip}" if vip is not None else "VIP未设置"
        rows.append([
            InlineKeyboardButton(
                f"{star}{site['name']} · {account_name} · {vip_text}",
                callback_data=f"acct:{account['id']}",
            )
        ])
    rows.append([InlineKeyboardButton("临时查询（不使用会员账户）", callback_data="guest")])
    return InlineKeyboardMarkup(rows)


def sites_keyboard(sites: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(site["name"], callback_data=f"site:{site['id']}")]
        for site in sites
    ]
    rows.append([InlineKeyboardButton("取消", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def amount_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("100", callback_data="amt:100"),
            InlineKeyboardButton("1,000", callback_data="amt:1000"),
        ],
        [
            InlineKeyboardButton("10,000", callback_data="amt:10000"),
            InlineKeyboardButton("100,000", callback_data="amt:100000"),
        ],
        [InlineKeyboardButton("自定义金额", callback_data="amt:custom")],
        [InlineKeyboardButton("重新开始", callback_data="restart")],
    ])


def basis_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("投注", callback_data="basis:bet"),
            InlineKeyboardButton("充值", callback_data="basis:deposit"),
        ],
        [InlineKeyboardButton("重新开始", callback_data="restart")],
    ])


def category_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(CATEGORIES), 2):
        rows.append([
            InlineKeyboardButton(label, callback_data=f"cat:{value}")
            for value, label in CATEGORIES[i:i + 2]
        ])
    rows.append([InlineKeyboardButton("重新开始", callback_data="restart")])
    return InlineKeyboardMarkup(rows)


def venues_keyboard(venues: list[dict[str, Any]], selected: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [[
        InlineKeyboardButton("全选", callback_data="venues:all"),
        InlineKeyboardButton("全不选", callback_data="venues:none"),
    ]]
    for i in range(0, len(venues), 2):
        row: list[InlineKeyboardButton] = []
        for venue in venues[i:i + 2]:
            code = str(venue["code"])
            prefix = "✅ " if code in selected else "▫️ "
            row.append(InlineKeyboardButton(f"{prefix}{venue['name']}", callback_data=f"venue:{code}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("查询活动", callback_data="venues:done")])
    rows.append([InlineKeyboardButton("重新开始", callback_data="restart")])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reset_flow(context)
    user = update.effective_user
    if not user:
        return
    try:
        accounts = await get_member_accounts(user.id)
        context.user_data["accounts"] = {row["id"]: row for row in accounts}
        if accounts:
            await update.effective_message.reply_text(
                "请选择会员账户。账户会自动带入站点和 VIP 等级；也可以临时查询。",
                reply_markup=account_keyboard(accounts),
            )
            return

        sites = await get_sites()
        context.user_data["sites"] = {row["id"]: row for row in sites}
        if not sites:
            await update.effective_message.reply_text("目前还没有启用的站点，请先在后台配置站点。")
            return
        await update.effective_message.reply_text(
            "当前 Telegram 尚未绑定会员账户，请先选择站点进行临时查询。",
            reply_markup=sites_keyboard(sites),
        )
    except Exception:
        log.exception("start failed")
        await update.effective_message.reply_text("读取会员资料失败，请稍后再试。")


async def show_amount_prompt(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    account_name = context.user_data.get("account_name")
    site_name = context.user_data.get("site_name", "")
    vip = context.user_data.get("vip")
    detail = site_name
    if account_name:
        detail += f" · {account_name}"
    if vip is not None:
        detail += f" · VIP{vip}"
    await query.edit_message_text(
        f"当前：{detail}\n\n请选择金额，或输入自定义金额。",
        reply_markup=amount_keyboard(),
    )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = query.data or ""

    if data in {"restart", "cancel"}:
        await query.edit_message_text("已重置。发送 /start 重新开始。")
        reset_flow(context)
        return

    if data == "guest":
        sites = await get_sites()
        context.user_data["sites"] = {row["id"]: row for row in sites}
        if not sites:
            await query.edit_message_text("目前还没有启用的站点，请先在后台配置站点。")
            return
        await query.edit_message_text("请选择站点：", reply_markup=sites_keyboard(sites))
        return

    if data.startswith("acct:"):
        account_id = data.split(":", 1)[1]
        account = (context.user_data.get("accounts") or {}).get(account_id)
        if not account:
            await query.edit_message_text("会员账户已失效，请发送 /start 重新读取。")
            return
        context.user_data["site_id"] = account["site_id"]
        context.user_data["site_name"] = account["site"]["name"]
        context.user_data["account_name"] = account.get("account_name")
        context.user_data["vip"] = account.get("vip_level")
        await show_amount_prompt(query, context)
        return

    if data.startswith("site:"):
        site_id = data.split(":", 1)[1]
        site = (context.user_data.get("sites") or {}).get(site_id)
        if not site:
            sites = await get_sites()
            site = next((row for row in sites if row["id"] == site_id), None)
        if not site:
            await query.edit_message_text("站点不存在或已停用，请发送 /start 重试。")
            return
        context.user_data["site_id"] = site_id
        context.user_data["site_name"] = site["name"]
        context.user_data["vip"] = None
        context.user_data["account_name"] = None
        await show_amount_prompt(query, context)
        return

    if data.startswith("amt:"):
        value = data.split(":", 1)[1]
        if value == "custom":
            context.user_data["awaiting_amount"] = True
            await query.edit_message_text("请输入金额，例如：1500")
            return
        context.user_data["amount"] = float(value)
        context.user_data["awaiting_amount"] = False
        await query.edit_message_text("这个金额属于哪一种？", reply_markup=basis_keyboard())
        return

    if data.startswith("basis:"):
        context.user_data["amount_basis"] = data.split(":", 1)[1]
        await query.edit_message_text("请选择分类：", reply_markup=category_keyboard())
        return

    if data.startswith("cat:"):
        category = data.split(":", 1)[1]
        context.user_data["category"] = category
        params = {
            "site_id": context.user_data["site_id"],
            "category": category,
            "meta": 1,
        }
        try:
            catalog = await fetch_catalog(params)
            venues = catalog.get("venues") or []
        except Exception:
            log.exception("venue load failed")
            await query.edit_message_text("场馆加载失败，请发送 /start 重试。")
            return
        context.user_data["venues"] = venues
        context.user_data["selected_venues"] = {str(v["code"]) for v in venues}
        if not venues:
            await run_query(query, context)
            return
        selected = context.user_data["selected_venues"]
        await query.edit_message_text(
            f"请选择场馆（可多选）。\n当前已选 {len(selected)}/{len(venues)} 个。\n全不选 = 不限制场馆。",
            reply_markup=venues_keyboard(venues, selected),
        )
        return

    if data == "venues:all":
        venues = context.user_data.get("venues") or []
        selected = {str(v["code"]) for v in venues}
        context.user_data["selected_venues"] = selected
        await query.edit_message_text(
            f"请选择场馆（可多选）。\n当前已选 {len(selected)}/{len(venues)} 个。\n全不选 = 不限制场馆。",
            reply_markup=venues_keyboard(venues, selected),
        )
        return

    if data == "venues:none":
        venues = context.user_data.get("venues") or []
        selected: set[str] = set()
        context.user_data["selected_venues"] = selected
        await query.edit_message_text(
            f"请选择场馆（可多选）。\n当前已选 0/{len(venues)} 个。\n全不选 = 不限制场馆。",
            reply_markup=venues_keyboard(venues, selected),
        )
        return

    if data == "venues:done":
        await run_query(query, context)
        return

    if data.startswith("venue:"):
        code = data.split(":", 1)[1]
        venues = context.user_data.get("venues") or []
        selected = set(context.user_data.get("selected_venues") or set())
        if code in selected:
            selected.remove(code)
        else:
            selected.add(code)
        context.user_data["selected_venues"] = selected
        await query.edit_message_text(
            f"请选择场馆（可多选）。\n当前已选 {len(selected)}/{len(venues)} 个。\n全不选 = 不限制场馆。",
            reply_markup=venues_keyboard(venues, selected),
        )


async def custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get("awaiting_amount"):
        return
    text = (update.effective_message.text or "").replace(",", "").strip()
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("金额格式不正确，请输入大于 0 的数字，例如：1500")
        return
    context.user_data["amount"] = amount
    context.user_data["awaiting_amount"] = False
    await update.effective_message.reply_text("这个金额属于哪一种？", reply_markup=basis_keyboard())


async def run_query(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    params: dict[str, Any] = {
        "site_id": context.user_data["site_id"],
        "amount": context.user_data["amount"],
        "amount_basis": context.user_data.get("amount_basis", "bet"),
        "category": context.user_data.get("category", "all"),
        "venues": ",".join(sorted(context.user_data.get("selected_venues") or [])),
    }
    vip = context.user_data.get("vip")
    if vip is not None:
        params["vip"] = vip

    await query.edit_message_text("正在查询活动…")
    try:
        result = await fetch_catalog(params)
        promotions = result.get("promotions") or []
    except Exception:
        log.exception("catalog query failed")
        await query.edit_message_text("查询失败，请稍后重试或发送 /start 重新开始。")
        return

    if not promotions:
        await query.edit_message_text(
            "当前条件暂未匹配到活动。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("重新查询", callback_data="restart")]]),
        )
        return

    basis_label = "充值" if params["amount_basis"] == "deposit" else "投注"
    lines = [
        f"✅ 共匹配 {len(promotions)} 个活动",
        f"站点：{context.user_data.get('site_name', '')}",
        f"金额：{float(params['amount']):,.2f}（{basis_label}）",
    ]
    if vip is not None:
        lines.append(f"VIP：VIP{vip}")
    lines.append("")

    for idx, promo in enumerate(promotions[:10], 1):
        lines.append(f"{idx}. {promo.get('title', '未命名活动')}")
        estimated = promo.get("estimated_bonus")
        if estimated is not None:
            lines.append(f"   预计彩金：{float(estimated):,.2f}")
        vip_min = promo.get("vip_min")
        vip_max = promo.get("vip_max")
        if vip is None and (vip_min is not None or vip_max is not None):
            if vip_min is not None and vip_max is not None:
                lines.append(f"   VIP条件：VIP{vip_min}–VIP{vip_max}")
            elif vip_min is not None:
                lines.append(f"   VIP条件：VIP{vip_min}+")
            else:
                lines.append(f"   VIP条件：最高 VIP{vip_max}")
        turnover = promo.get("turnover_multiple")
        if turnover is not None:
            lines.append(f"   流水：{turnover} 倍")
        summary = promo.get("summary")
        if summary:
            lines.append(f"   {summary}")
        frontend_url = promo.get("frontend_url")
        if frontend_url:
            lines.append(f"   {frontend_url}")
        lines.append("")

    if len(promotions) > 10:
        lines.append(f"另有 {len(promotions) - 10} 个活动未在本条消息展开。")

    await query.edit_message_text(
        "\n".join(lines)[:3900],
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("重新查询", callback_data="restart")]]),
    )


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, custom_amount))
    log.info("Bot started with long polling")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
