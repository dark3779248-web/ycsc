# FinWise 开发文档

本目录用于后期审核和理解项目。所有 FinWise 相关代码、数据库迁移、设计资源和开发说明必须保存在 `finwise-app/` 内。

## 阅读顺序

1. [ARCHITECTURE.md](./ARCHITECTURE.md)：系统由什么组成，以及各部分如何通信。
2. [REVIEW_GUIDE.md](./REVIEW_GUIDE.md)：如何逐项审核功能和安全性。
3. [CHANGELOG.md](./CHANGELOG.md)：每次重要改动、原因和影响。
4. [SECURITY.md](./SECURITY.md)：权限、密钥、资金和上线边界。

## 目录规则

```text
finwise-app/
├── docs/                    # 审核、原理和变更文档
├── public/figma/            # 从 Figma 导出的界面资源
├── src/app/                 # Next.js 页面和样式
├── src/lib/supabase/        # Supabase 浏览器通信代码
├── supabase/migrations/     # 可追踪、可复核的数据库变更
├── .env.example             # 环境变量名称示例，不含秘密
└── README.md                # 项目入口说明
```

不允许把密码、数据库私钥、银行卡资料、用户隐私或 `.env.local` 提交到 GitHub。
