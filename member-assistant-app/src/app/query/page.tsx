'use client';
import {FormEvent,useEffect,useState} from 'react';
import {createBrowserSupabase} from '@/lib/supabase/client';

type Result={id:string;title:string;description:string|null;benefit_type:string;value_json:any};
const categories=[['all','全站'],['sports','体育'],['live','真人'],['esports','电竞'],['chess','棋牌'],['slots','电子'],['entertainment','娱乐'],['lottery','彩票']];
function guestId(){let id=localStorage.getItem('member_assistant_guest_session');if(!id){id=crypto.randomUUID();localStorage.setItem('member_assistant_guest_session',id)}return id}

export default function Query(){
 const [logged,setLogged]=useState(false);const [site,setSite]=useState('');const [amount,setAmount]=useState('1000');const [category,setCategory]=useState('all');const [results,setResults]=useState<Result[]>([]);const [msg,setMsg]=useState('');
 useEffect(()=>{createBrowserSupabase().auth.getUser().then(({data})=>setLogged(!!data.user));},[]);
 async function submit(e:FormEvent){e.preventDefault();setMsg('查询中…');const payload={session_id:guestId(),site,amount:Number(amount),category,venues:[]};const r=await fetch('/api/public/query',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});const d=await r.json();if(!r.ok){setMsg(d.error||'查询失败');return;}setResults(d.data||[]);setMsg(`找到 ${d.data?.length||0} 项可参考权益${logged?'，已登录账户可继续查看个人权益':'；本次仅记录匿名查询，不保存会员账户资料'}`);}
 return <main className="shell"><header className="top"><div><div className="brand">会员权益查询</div><div className="muted">无需登录即可查询；登录后才保存会员账户与个人数据。</div></div><a href={logged?'/':'/login'}>{logged?'会员中心':'登录'}</a></header><form className="card form" style={{margin:'20px 0'}} onSubmit={submit}><input className="input" value={site} onChange={e=>setSite(e.target.value)} placeholder="选择或输入站点" required/><div style={{display:'flex',gap:8,flexWrap:'wrap'}}>{['100','1000','10000','100000'].map(x=><button type="button" className="btn secondary" key={x} onClick={()=>setAmount(x)}>{Number(x).toLocaleString()}</button>)}</div><input className="input" value={amount} onChange={e=>setAmount(e.target.value)} type="number" min="1" placeholder="金额" required/><select className="input" value={category} onChange={e=>setCategory(e.target.value)}>{categories.map(([v,n])=><option key={v} value={v}>{n}</option>)}</select><button className="btn">立即查询</button><div className="status">{msg}</div></form><section className="list">{results.map(x=><div className="card" key={x.id}><h2>{x.title}</h2><div className="muted">{x.description||'暂无说明'}</div></div>)}</section>{!logged?<div className="card" style={{marginTop:16}}><b>登录是可选的</b><div className="muted">不登录照常查询。登录后才会保存你的会员账户、等级、常用条件、历史偏好，并提供个人提醒和 Telegram 绑定。</div></div>:null}</main>;
}
