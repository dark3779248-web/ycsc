# 会员福利助手 Telegram Bot

第一版流程：

- `/start`
- 已绑定会员：选择会员账户（自动带入站点 + VIP）
- 未绑定/临时查询：选择站点
- 选择快捷金额或输入自定义金额
- 单选：投注 / 充值
- 选择分类
- 场馆支持多选、全选、全不选
- 查询活动

活动匹配统一调用 H5 的 `/api/catalog`，避免 Telegram 与 H5 使用不同规则。

## VPS 部署

```bash
cd /opt/ycsc
git pull
cd /opt/ycsc/huiyuanzhushou/bot
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

`.env` 填入：

```env
TELEGRAM_BOT_TOKEN=你的BotFatherToken
SUPABASE_URL=https://pefunmkcrofwmgurlktn.supabase.co
SUPABASE_SERVICE_ROLE_KEY=你的Supabase服务端密钥
CATALOG_API_URL=https://huiyuanzhushou.vercel.app/api/catalog
```

不要提交 `.env`。

安装 systemd：

```bash
cp huiyuanzhushou-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now huiyuanzhushou-bot
systemctl status huiyuanzhushou-bot --no-pager
```

查看日志：

```bash
journalctl -u huiyuanzhushou-bot -f
```

## 会员账户识别

机器人用 Telegram user id 查询 `member_contact_channels.external_account_id`，找到对应 `user_id` 后，再读取 `member_site_accounts`。因此只有已经完成 Telegram 绑定的会员，`/start` 时才会直接出现会员账户；没有绑定的用户自动进入临时查询流程。
