'use client';

import { FormEvent, useEffect, useState } from 'react';

type Site = { id: string; code: string; name: string };
type Venue = { id: string; site_id: string; category: string; code: string; name: string };
type Promotion = {
  id: string;
  title: string;
  summary?: string | null;
  frontend_url?: string | null;
  application_method?: string | null;
  turnover_multiple?: number | null;
  estimated_bonus?: number | null;
};

const categories = [
  ['all', '全站'], ['sports', '体育'], ['live', '真人'], ['esports', '电竞'],
  ['chess', '棋牌'], ['slots', '电子'], ['entertainment', '娱乐'], ['lottery', '彩票'],
];

export default function Home() {
  const [sites, setSites] = useState<Site[]>([]);
  const [venues, setVenues] = useState<Venue[]>([]);
  const [selectedVenues, setSelectedVenues] = useState<string[]>([]);
  const [siteId, setSiteId] = useState('');
  const [amount, setAmount] = useState('1000');
  const [category, setCategory] = useState('all');
  const [results, setResults] = useState<Promotion[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetch('/api/catalog').then(r => r.json()).then(data => {
      setSites(data.sites || []);
      if (data.sites?.[0]?.id) setSiteId(data.sites[0].id);
    }).catch(() => setMessage('站点加载失败，请稍后重试'));
  }, []);

  useEffect(() => {
    if (!siteId) {
      setVenues([]);
      setSelectedVenues([]);
      return;
    }
    fetch(`/api/catalog?site_id=${encodeURIComponent(siteId)}&category=${encodeURIComponent(category)}&meta=1`)
      .then(r => r.json())
      .then(data => {
        const nextVenues = data.venues || [];
        setVenues(nextVenues);
        setSelectedVenues(nextVenues.map((v: Venue) => v.code));
      })
      .catch(() => {
        setVenues([]);
        setSelectedVenues([]);
      });
  }, [siteId, category]);

  function toggleVenue(code: string) {
    setSelectedVenues(current => current.includes(code)
      ? current.filter(v => v !== code)
      : [...current, code]);
  }

  async function query(e: FormEvent) {
    e.preventDefault();
    if (!siteId) return setMessage('请先选择站点');
    setLoading(true);
    setMessage('');
    try {
      const venueParam = selectedVenues.join(',');
      const r = await fetch(`/api/catalog?site_id=${encodeURIComponent(siteId)}&amount=${encodeURIComponent(amount)}&category=${encodeURIComponent(category)}&venues=${encodeURIComponent(venueParam)}`);
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || '查询失败');
      setResults(data.promotions || []);
      if (!data.promotions?.length) setMessage('当前条件暂未匹配到活动');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '查询失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <section className="hero">
        <span className="eyebrow">MEMBER BENEFITS</span>
        <h1>会员福利助手</h1>
        <p>不登录也可以查询。选择站点、金额、分类和场馆，快速查看当前可参与活动与预计彩金。</p>
      </section>

      <form className="panel" onSubmit={query}>
        <label>站点<select value={siteId} onChange={e => setSiteId(e.target.value)}>{sites.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
        <label>金额<input inputMode="decimal" value={amount} onChange={e => setAmount(e.target.value)} placeholder="请输入金额" /></label>
        <div><div className="label">分类</div><div className="chips">{categories.map(([value, label]) => <button type="button" key={value} className={category === value ? 'chip active' : 'chip'} onClick={() => setCategory(value)}>{label}</button>)}</div></div>
        {venues.length > 0 && <div><div className="label">场馆</div><div className="chips">{venues.map(v => <button type="button" key={v.id} className={selectedVenues.includes(v.code) ? 'chip active' : 'chip'} onClick={() => toggleVenue(v.code)}>{v.name}</button>)}</div></div>}
        <button className="primary" disabled={loading}>{loading ? '查询中…' : '查询可参与活动'}</button>
      </form>

      {message && <p className="message">{message}</p>}

      <section className="results">
        {results.map((p, i) => <article className="card" key={`${p.id}-${i}`}>
          <div className="cardTop"><h2>{p.title}</h2>{p.estimated_bonus !== null && p.estimated_bonus !== undefined && <strong>预计 {Number(p.estimated_bonus).toLocaleString()} 元</strong>}</div>
          {p.summary && <p>{p.summary}</p>}
          <div className="meta">
            {p.turnover_multiple !== null && p.turnover_multiple !== undefined && <span>流水 {p.turnover_multiple} 倍</span>}
            {p.application_method && <span>{p.application_method}</span>}
          </div>
          {p.frontend_url && <a href={p.frontend_url} target="_blank" rel="noreferrer">查看活动详情 →</a>}
        </article>)}
      </section>

      <footer>登录后可保存会员账户、VIP 等级和常用查询偏好。</footer>
    </main>
  );
}
