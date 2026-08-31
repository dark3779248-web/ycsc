import './globals.css';

export const metadata = {
  title: '会员福利助手',
  description: '查询可参与活动与预计权益',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
