'use client';
import { useState } from 'react';
import { createBrowserSupabase } from '@/lib/supabase/client';

export default function TelegramBind(){
  const [code,setCode]=useState('');const [expires,setExpires]=useState('');const [msg,setMsg]=useState('');
  async function createCode(){
    const s=createBrowserSupabase();const {data:{session}}=await s.auth.getSession();
    if(!session){location.href='/login';return;}
    const r=await fetch('/api/telegram/bind-code',{method:'POST',headers:{Authorization:`Bearer ${session.access_token}`}});
    const d=await r.json();if(!r.ok){setMsg(d.error||'生成失败');return;}
    setCode(d.code);setExpires(d.expires_at);setMsg('请在 10 分钟内发送给机器人。');
  }
  return <main className="shell"><div className="top"><div className="brand">绑定 Telegram</div><a href="/">返回</a></div><section className="card" style={{marginTop:20,maxWidth:680}}><h2>绑定你的 Telegram</h2><p className="muted">先生成一次性绑定码，然后到会员助手 Bot 发送：</p>{code?<><div className="big">/bind {code}</div><p className="muted">有效期至：{new Date(expires).toLocaleString()}</p></>:null}<button className="btn" onClick={createCode}>{code?'重新生成绑定码':'生成绑定码'}</button><div className="status">{msg}</div></section></main>;
}
