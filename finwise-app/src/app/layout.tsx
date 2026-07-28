import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinWise 预测市场",
  description: "智能预测市场与交易分析平台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
