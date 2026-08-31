import './globals.css';

export const metadata = { title: '会员权益助手', description: '会员权益、通知、客服与导航' };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
