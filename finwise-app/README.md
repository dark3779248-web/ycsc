# FinWise 预测市场

FinWise 是基于 Next.js、Supabase 和 Vercel 的预测市场 MVP。目前只使用 FW 模拟积分，不涉及真实资金。

## 开发文档

审核和原理说明从 [docs/README.md](./docs/README.md) 开始阅读。

## 项目边界

- 所有 FinWise 文件必须保存在本 `finwise-app/` 目录中。
- 数据库变化必须保存在 `supabase/migrations/`。
- 重要改动必须记录到 `docs/CHANGELOG.md`。
- `.env.local` 不得提交到 GitHub。

## 本地开发

```bash
pnpm dev
```

打开 `http://localhost:3000`。主要入口：

- 页面：`src/app/page.tsx`
- 样式：`src/app/globals.css`
- Supabase 通信：`src/lib/supabase/client.ts`
- 数据库：`supabase/migrations/`

## 验证

```bash
pnpm run lint
pnpm run build
```

生产环境由 GitHub `main` 自动部署到 [FinWise](https://ycsc-chi.vercel.app/)。
