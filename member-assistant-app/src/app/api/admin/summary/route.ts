import { NextRequest, NextResponse } from 'next/server';
import { requireAdmin } from '@/lib/supabase/admin';

export async function GET(req: NextRequest) {
  const token=req.headers.get('authorization')?.replace(/^Bearer\s+/i,'');
  if(!token)return NextResponse.json({error:'unauthorized'},{status:401});
  try{
    const {supabase,admin}=await requireAdmin(token);
    const [members,support,feedback,delivery]=await Promise.all([
      supabase.from('membership_accounts').select('*',{count:'exact',head:true}),
      supabase.from('support_conversations').select('*',{count:'exact',head:true}).in('status',['open','pending']),
      supabase.from('feedback_requests').select('*',{count:'exact',head:true}).in('status',['submitted','reviewing']),
      supabase.from('member_notification_deliveries').select('*',{count:'exact',head:true}).in('status',['queued','failed']),
    ]);
    return NextResponse.json({members:members.count||0,openSupport:support.count||0,pendingFeedback:feedback.count||0,undelivered:delivery.count||0,adminName:admin.display_name||admin.role});
  }catch(e){return NextResponse.json({error:e instanceof Error?e.message:'forbidden'},{status:403});}
}
