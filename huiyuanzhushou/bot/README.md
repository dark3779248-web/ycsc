# 会员福利助手 Telegram Bot

第一版流程：

- `/start`：打开或刷新查询面板，并关闭之前未完成的旧面板
- `/account`：添加或管理会员账户
- `/close`：关闭当前查询
- `/help`：查看使用说明
- 已绑定会员：选择会员账户（自动带入站点 + VIP）
- 未注册用户也可从“会员账户 / 站点”中直接添加并保存会员账户
- 未绑定/临时查询：选择站点
- 选择快捷金额或输入自定义金额
- 自定义金额保持原查询面板，并直接唤起输入框
- 已选金额、类型、分类和场馆使用蓝色按钮标识
- 单选：充值 / 投注
- 选择分类
- 场馆支持多选、全选、不限场馆；再次点击已选场馆可取消
- 查询活动

活动匹配统一调用 H5 的 `/api/catalog`，避免 Telegram 与 H5 使用不同规则。

机器人启动时会自动配置 Telegram 底部命令菜单。加入群组后只响应明确命令；会员账户、查询条件与活动结果仍只在机器人私聊中展示。

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
BOT_DESCRIPTION=首次打开空白聊天时显示的宣传介绍（最多 512 字）
BOT_SHORT_DESCRIPTION=机器人资料页和分享链接中的短介绍（最多 120 字）
WELCOME_IMAGE_URL=点击 Start 后发送的宣传图片公网地址（可留空）
WELCOME_TEXT=宣传图片说明文字（可留空）
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

## 自动部署

GitHub Actions 会在 `main` 分支中的 `huiyuanzhushou` 目录更新后，先运行机器人测试；测试通过后自动连接 VPS，拉取代码并重新构建 `telegram-bot` 容器。部署使用仓库 Actions Secrets 中的 `VPS_HOST`、`VPS_PORT`、`VPS_USER` 和 `VPS_SSH_KEY`。

## 会员账户识别

机器人用 Telegram user id 查询 `member_contact_channels.external_account_id`，再通过 `membership_id` 读取 `member_site_accounts`。第一次添加账户时会自动建立 Telegram 轻量会员身份，以后仍可再与 H5 登录身份合并。
