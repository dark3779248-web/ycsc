import { NextRequest, NextResponse } from 'next/server';
import { createAdminSupabase } from '@/lib/supabase/admin';

export async function POST(req: NextRequest) {
  const token=req.headers.get('authorization')?.replace(/^Bearer\s+/i,'');
  if(!token)return NextResponse.json({error:'unauthorized'},{status:401});
  const s=createAdminSupabase();
  const {data:{user},error}=await s.auth.getUser(token);
  if(error||!user)return NextResponse.json({error:'unauthorized'},{status:401});
  const {data:membership}=await s.from('membership_accounts').select('id').eq('user_id',user.id).maybeSingle();
  const code=Math.random().toString(36).slice(2,8).toUpperCase();
  const expiresAt=new Date(Date.now()+10*60*1000).toISOString();
  await s.from('telegram_binding_codes').delete().eq('user_id',user.id).is('used_at',null);
  const r=await s.from('telegram_binding_codes').insert({user_id:user.id,membership_id:membership?.id||null,code,expires_at:expiresAt}).select('code,expires_at').single();
  if(r.error)return NextResponse.json({error:r.error.message},{status:400});
  return NextResponse.json(r.data);
}
