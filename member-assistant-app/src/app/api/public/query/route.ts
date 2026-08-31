import { NextRequest,NextResponse } from 'next/server';
import { createAdminSupabase } from '@/lib/supabase/admin';

const allowedCategories=['all','sports','live','esports','chess','slots','entertainment','lottery'];

export async function POST(req:NextRequest){
  try{
    const body=await req.json();
    const sessionId=String(body.session_id||'');
    const site=String(body.site||'').trim().slice(0,80);
    const amount=Number(body.amount||0);
    const category=String(body.category||'all');
    const venues=Array.isArray(body.venues)?body.venues.slice(0,20).map((x:unknown)=>String(x).slice(0,80)):[];
    if(!/^[0-9a-f-]{36}$/i.test(sessionId)||!site||!Number.isFinite(amount)||amount<=0||!allowedCategories.includes(category)) return NextResponse.json({error:'查询条件不完整'},{status:400});
    const s=createAdminSupabase();
    // 当前阶段先返回已启用、符合最低等级 0 的公开权益；后续活动规则库接入后在这里计算站点/金额/场馆匹配。
    const {data,error}=await s.from('member_benefits').select('id,code,title,description,benefit_type,value_json,starts_at,expires_at').eq('is_enabled',true).lte('min_member_level',0).or(`starts_at.is.null,starts_at.lte.${new Date().toISOString()}`).or(`expires_at.is.null,expires_at.gte.${new Date().toISOString()}`).order('sort_order');
    if(error)throw error;
    const results=data||[];
    await s.from('guest_query_logs').insert({session_id:sessionId,site,amount,category,venues,query_payload:{site,amount,category,venues},result_summary:{count:results.length,benefit_codes:results.map(x=>x.code).slice(0,30)},user_agent:req.headers.get('user-agent')?.slice(0,500)||null});
    return NextResponse.json({data:results,guest:true});
  }catch(e){return NextResponse.json({error:e instanceof Error?e.message:'查询失败'},{status:500});}
}
