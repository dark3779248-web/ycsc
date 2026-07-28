"use client";

import Image from "next/image";
import { useState } from "react";

const categories = ["热门", "虚拟币", "政治", "体育", "电竞", "娱乐"];
const navItems = [
  ["首页", "/figma/home.svg"],
  ["活动", "/figma/gift.svg"],
  ["客服", "/figma/headset.svg"],
  ["我的", "/figma/user.svg"],
];

const markets = [
  {
    title: "BTC 是否会在 8 月突破 10 万美元?",
    volume: "$1.2M",
    people: "1.4K",
    days: 15,
    yes: 64,
    no: 36,
    color: "#00d09e",
    bars: [8, 12, 10, 16, 14, 20, 18, 22, 24, 22, 20],
  },
  {
    title: "美国SEC是否会在下月批准 Solana 现货 ETF?",
    volume: "$450K",
    people: "850",
    days: 28,
    yes: 55,
    no: 45,
    color: "#ff4d4d",
    bars: [8, 12, 10, 16, 14, 20, 18, 22, 24, 22, 20],
  },
];

export default function Home() {
  const [category, setCategory] = useState("热门");
  const [activeNav, setActiveNav] = useState("首页");
  const [selection, setSelection] = useState<string | null>(null);
  const [notice, setNotice] = useState(false);

  return (
    <main className="stage">
      <section className="phone" aria-label="预测市场移动端首页">
        <div className="statusbar">
          <strong>16:04</strong>
          <div className="status-icons">
            <Image src="/figma/ios-signal.svg" alt="信号" width={18} height={12} />
            <Image src="/figma/ios-battery.svg" alt="电量" width={24} height={12} />
          </div>
        </div>

        <header className="header">
          <div className="brand">
            <Image className="logo" src="/figma/app-logo.png" alt="FinWise" width={32} height={32} />
            <h1>预测市场</h1>
          </div>
          <button className="icon-button" onClick={() => setNotice(!notice)} aria-label="通知">
            <Image src="/figma/bell.svg" alt="" width={24} height={24} />
            {notice && <span className="dot" />}
          </button>
        </header>

        <div className="scroll-area">
          <div className="content">
            <button className="banner" onClick={() => setNotice(true)}>
              <strong>FinWise 新用户福利</strong>
              <span>注册即送 $10 体验金，预测赚取高达 100x 收益！</span>
            </button>

            <div className="chips" aria-label="市场分类">
              {categories.map((item) => (
                <button key={item} className={category === item ? "chip active" : "chip"} onClick={() => setCategory(item)}>
                  {item}
                </button>
              ))}
            </div>

            <div className="section-title"><h2>{category === "热门" ? "热门预测" : `${category}预测`}</h2><button>查看全部</button></div>

            {markets.map((market, marketIndex) => (
              <article className="market-card" key={market.title}>
                <button className="market-title"><strong>{market.title}</strong><Image src="/figma/chevron-right.svg" alt="查看详情" width={16} height={16} /></button>
                <div className="sparkline" aria-hidden="true">
                  {market.bars.map((height, index) => <i key={index} style={{ height, backgroundColor: market.color }} />)}
                </div>
                <div className="meta">
                  <span>交易量: {market.volume}・{market.people} 参与</span>
                  <span className="deadline"><Image src="/figma/clock.svg" alt="" width={12} height={12} />{market.days}天后截止</span>
                </div>
                <div className="actions">
                  <button className={selection === `${marketIndex}-yes` ? "yes selected" : "yes"} onClick={() => setSelection(`${marketIndex}-yes`)}>Yes ¢{market.yes}</button>
                  <button className={selection === `${marketIndex}-no` ? "no selected" : "no"} onClick={() => setSelection(`${marketIndex}-no`)}>No ¢{market.no}</button>
                </div>
              </article>
            ))}

            <div className="section-title urgent-title"><h2>即将截止 <em>紧急</em></h2><button>查看全部</button></div>
            <article className="urgent-card">
              <strong>以太坊 Gas 费在今日结束前是否会突破 50 Gwei?</strong>
              <div><b>仅剩 02:45:12</b><span>Yes ¢15 / No ¢85</span></div>
            </article>
          </div>
        </div>

        <nav className="bottom-nav">
          {navItems.slice(0, 2).map(([label, icon]) => <NavButton key={label} label={label} icon={icon} active={activeNav === label} onClick={setActiveNav} />)}
          <button className="ai-button" aria-label="AI 助手"><Image src="/figma/brain.svg" alt="" width={24} height={24} /></button>
          {navItems.slice(2).map(([label, icon]) => <NavButton key={label} label={label} icon={icon} active={activeNav === label} onClick={setActiveNav} />)}
        </nav>
      </section>
    </main>
  );
}

function NavButton({ label, icon, active, onClick }: { label: string; icon: string; active: boolean; onClick: (label: string) => void }) {
  return <button className={active ? "nav-item active" : "nav-item"} onClick={() => onClick(label)}><Image src={icon} alt="" width={20} height={20} /><span>{label}</span></button>;
}
