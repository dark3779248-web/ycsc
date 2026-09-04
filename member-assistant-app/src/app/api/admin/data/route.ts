import { NextRequest, NextResponse } from 'next/server';
import { requireAdmin } from '@/lib/supabase/admin';

const allowed = new Set(['members','benefits','feedback','support','navigation','notifications']);

export async function GET(req: NextRequest) {
  const token = req.headers.get('authorization')?.replace(/^Bearer\s+/i,'');
  if (!token) return NextResponse.json({ error:'unauthorized' }, { status:401 });
  const section = req.nextUrl.searchParams.get('section') || 'members';
  if (!allowed.has(section)) return NextResponse.json({ error:'bad_section' }, { status:400 });

  try {
    const { supabase } = await requireAdmin(token);
    let data:any[] = [];
    if (section === 'members') {
      const r = await supabase.from('membership_accounts').select('id,user_id,member_no,account_name,status,level,starts_at,expires_at,created_at').order('created_at',{ascending:false}).limit(200);
      if (r.error) throw r.error; data = r.data || [];
    } else if (section === 'benefits') {
      const r = await supabase.from('member_benefits').select('*').order('sort_order').order('created_at',{ascending:false}).limit(200);
      if (r.error) throw r.error; data = r.data || [];
    } else if (section === 'feedback') {
      const r = await supabase.from('feedback_requests').select('id,user_id,feedback_type,title,desired_feature,current_problem,use_case,desired_outcome,status,priority,admin_note,submitted_at,updated_at').order('submitted_at',{ascending:false}).limit(200);
      if (r.error) throw r.error; data = r.data || [];
    } else if (section === 'support') {
      const r = await supabase.from('support_conversations').select('id,user_id,subject,status,priority,last_message_at,created_at').order('last_message_at',{ascending:false}).limit(200);
      if (r.error) throw r.error;
      const ids=(r.data||[]).map(x=>x.id);
      const m=ids.length?await supabase.from('support_messages').select('id,conversation_id,sender_role,body,created_at').in('conversation_id',ids).order('created_at',{ascending:true}):{data:[],error:null};
      if (m.error) throw m.error;
      data=(r.data||[]).map(c=>({...c,messages:(m.data||[]).filter(x=>x.conversation_id===c.id)}));
    } else if (section === 'navigation') {
      const r = await supabase.from('navigation_links').select('*').is('owner_user_id',null).order('sort_order').limit(200);
      if (r.error) throw r.error; data = r.data || [];
    } else if (section === 'notifications') {
      const r = await supabase.from('member_notification_messages').select('id,user_id,kind,title,body,status,scheduled_at,sent_at,read_at,created_at').order('created_at',{ascending:false}).limit(200);
      if (r.error) throw r.error; data = r.data || [];
    }
    return NextResponse.json({ data });
  } catch (e) {
    return NextResponse.json({ error:e instanceof Error?e.message:'forbidden' }, { status:403 });
  }
}
