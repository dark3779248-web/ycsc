'use client';
import { FormEvent,useState } from 'react';
import { createBrowserSupabase } from '@/lib/supabase/client';

export default function Feedback(){
 const [feature,setFeature]=useState('');const [problem,setProblem]=useState('');const [scene,setScene]=useState('');const [outcome,setOutcome]=useState('');const [files,setFiles]=useState<FileList|null>(null);const [msg,setMsg]=useState('');
 async function submit(e:FormEvent){
  e.preventDefault();setMsg('提交中…');const s=createBrowserSupabase();const {data:{user}}=await s.auth.getUser();if(!user){location.href='/login';return;}
  const {data:m}=await s.from('membership_accounts').select('id').eq('user_id',user.id).maybeSingle();
  const {data:feedback,error}=await s.from('feedback_requests').insert({user_id:user.id,membership_id:m?.id||null,feedback_type:'feature_request',desired_feature:feature,current_problem:problem,use_case:scene,desired_outcome:outcome}).select('id').single();
  if(error||!feedback){setMsg(error?.message||'提交失败');return;}
  const uploadErrors:string[]=[];
  for(const file of Array.from(files||[])){
   if(!file.type.startsWith('image/')){uploadErrors.push(`${file.name} 不是图片`);continue;}
   if(file.size>10*1024*1024){uploadErrors.push(`${file.name} 超过 10MB`);continue;}
   const safe=file.name.replace(/[^a-zA-Z0-9._-]/g,'_');const path=`${user.id}/${feedback.id}/${crypto.randomUUID()}-${safe}`;
   const up=await s.storage.from('feedback').upload(path,file,{upsert:false,contentType:file.type});
   if(up.error){uploadErrors.push(`${file.name}: ${up.error.message}`);continue;}
   const meta=await s.from('feedback_attachments').insert({feedback_id:feedback.id,user_id:user.id,storage_bucket:'feedback',storage_path:path,mime_type:file.type,file_size:file.size});
   if(meta.error)uploadErrors.push(`${file.name}: ${meta.error.message}`);
  }
  setMsg(uploadErrors.length?`建议已提交，但部分图片失败：${uploadErrors.join('；')}`:'已提交，我们会记录并跟进。');setFeature('');setProblem('');setScene('');setOutcome('');setFiles(null);
 }
 return <main className="shell"><div className="top"><div className="brand">建议反馈 / 功能许愿</div><a href="/">返回</a></div><form className="card form" style={{margin:'20px 0',maxWidth:720}} onSubmit={submit}><textarea className="input" rows={3} placeholder="你希望增加什么功能？" value={feature} onChange={e=>setFeature(e.target.value)} required/><textarea className="input" rows={3} placeholder="现在遇到什么问题？" value={problem} onChange={e=>setProblem(e.target.value)}/><textarea className="input" rows={3} placeholder="使用场景" value={scene} onChange={e=>setScene(e.target.value)}/><textarea className="input" rows={3} placeholder="实现后希望达到什么结果？" value={outcome} onChange={e=>setOutcome(e.target.value)}/><label className="muted">可选上传截图/图片（单张不超过 10MB）</label><input className="input" type="file" accept="image/*" multiple onChange={e=>setFiles(e.target.files)}/><button className="btn">提交建议</button><div className="status">{msg}</div></form></main>}
