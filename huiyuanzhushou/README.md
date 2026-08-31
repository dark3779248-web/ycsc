# 会员福利助手 H5

会员助手独立项目目录，部署到 Vercel，并连接现有 Supabase `fulizhushou`。

## 当前能力

- 游客无需登录即可选择站点、金额、分类查询活动。
- 查询只读取 Supabase 中启用的站点、活动和规则。
- 登录后的账户保存、VIP 偏好、Telegram 绑定将接入现有会员表。

## Vercel 环境变量

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`

Vercel 项目的 Root Directory 必须设为 `huiyuanzhushou`，不要关联 `finwise-app`。

## 本地验证

```bash
npm install
npm run build
```
