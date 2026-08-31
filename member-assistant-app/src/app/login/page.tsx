'use client';

import { FormEvent, useState } from 'react';
import { createBrowserSupabase } from '@/lib/supabase/client';

export default function LoginPage() {
  const [email,setEmail]=useState(''); const [password,setPassword]=useState(''); const [msg,setMsg]=useState('');
  async function submit(e:FormEvent){e.preventDefault();setMsg('登录中…');const supabase=createBrowserSupabase();const {error}=await supabase.auth.signInWithPassword({email,password});if(error){setMsg(error.message);return;}location.href='/';}
  return <main className="shell"><form className="form card" onSubmit={submit}><h1>会员助手登录</h1><input className="input" type="email" placeholder="邮箱" value={email} onChange={e=>setEmail(e.target.value)} required/><input className="input" type="password" placeholder="密码" value={password} onChange={e=>setPassword(e.target.value)} required/><button className="btn" type="submit">登录</button><div className="status">{msg}</div></form></main>;
}
