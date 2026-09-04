# 会员权益助手

独立于 `finwise-app` 的会员助手应用，基于 Next.js + Supabase。

## 当前第一版

- 会员登录与 H5 首页
- 我的权益
- 网站导航
- 会员通知
- 建议反馈 / 功能许愿
- 客服会话
- 管理后台汇总
- Telegram Bot Webhook：`/start`、`/benefits`、`/support`

## 环境变量

复制 `.env.example` 为 `.env.local`，补充 Supabase anon key、service role key、Telegram Bot token 与 webhook secret。

## 本地运行

```bash
npm install
npm run dev
```

## 管理员

管理员必须先是 Supabase Auth 用户，再由服务端写入 `public.member_admin_users`。该表不向 `anon/authenticated` 开放。

## Telegram 绑定

`member_contact_channels.channel_type = 'telegram_bot'`，`external_account_id` 保存 Telegram 用户 ID。Bot 不把陌生 Telegram ID 当成会员名单。
