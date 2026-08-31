import { NextRequest, NextResponse } from 'next/server';
import { requireAdmin } from '@/lib/supabase/admin';

export async function POST(req: NextRequest) {
  const token = req.headers.get('authorization')?.replace(/^Bearer\s+/i,'');
  if (!token) return NextResponse.json({ error:'unauthorized' }, { status:401 });
  try {
    const { supabase, user } = await requireAdmin(token);
    const body = await req.json();
    const action = String(body.action || '');

    if (action === 'member.update') {
      const { id, status, level, expires_at } = body;
      const r = await supabase.from('membership_accounts').update({ status, level:Number(level), expires_at:expires_at||null, updated_at:new Date().toISOString() }).eq('id',id).select().single();
      if (r.error) throw r.error; return NextResponse.json({ data:r.data });
    }

    if (action === 'benefit.upsert') {
      const payload = { code:body.code,title:body.title,description:body.description||null,benefit_type:body.benefit_type||'general',min_member_level:Number(body.min_member_level||0),is_enabled:body.is_enabled!==false,sort_order:Number(body.sort_order||0),updated_at:new Date().toISOString() };
      const r = body.id ? await supabase.from('member_benefits').update(payload).eq('id',body.id).select().single() : await supabase.from('member_benefits').insert(payload).select().single();
      if (r.error) throw r.error; return NextResponse.json({ data:r.data });
    }

    if (action === 'feedback.update') {
      const current = await supabase.from('feedback_requests').select('id,user_id,status').eq('id',body.id).single();
      if (current.error) throw current.error;
      const toStatus=String(body.status||current.data.status);
      const r=await supabase.from('feedback_requests').update({status:toStatus,priority:body.priority||'normal',admin_note:body.admin_note||null,updated_at:new Date().toISOString()}).eq('id',body.id).select().single();
      if(r.error)throw r.error;
      if(current.data.status!==toStatus){await supabase.from('feedback_status_history').insert({feedback_id:body.id,user_id:current.data.user_id,from_status:current.data.status,to_status:toStatus,note:body.admin_note||null,changed_by:user.id,change_source:'admin'});}
      return NextResponse.json({data:r.data});
    }

    if (action === 'support.reply') {
      const c=await supabase.from('support_conversations').select('id,user_id').eq('id',body.conversation_id).single(); if(c.error)throw c.error;
      const now=new Date().toISOString();
      const m=await supabase.from('support_messages').insert({conversation_id:c.data.id,user_id:c.data.user_id,sender_user_id:user.id,sender_role:'support',body:String(body.message||''),content_type:'text'}).select().single(); if(m.error)throw m.error;
      await supabase.from('support_conversations').update({status:body.status||'pending',last_message_at:now,updated_at:now}).eq('id',c.data.id);
      return NextResponse.json({data:m.data});
    }

    if (action === 'support.status') {
      const now=new Date().toISOString(); const status=String(body.status||'open');
      const r=await supabase.from('support_conversations').update({status,closed_at:status==='closed'?now:null,updated_at:now}).eq('id',body.id).select().single(); if(r.error)throw r.error; return NextResponse.json({data:r.data});
    }

    if (action === 'navigation.upsert') {
      const payload={owner_user_id:null,title:body.title,url:body.url,description:body.description||null,category:body.category||null,sort_order:Number(body.sort_order||0),is_enabled:body.is_enabled!==false,is_member_only:body.is_member_only!==false,min_member_level:Number(body.min_member_level||0),updated_at:new Date().toISOString()};
      const r=body.id?await supabase.from('navigation_links').update(payload).eq('id',body.id).select().single():await supabase.from('navigation_links').insert(payload).select().single(); if(r.error)throw r.error; return NextResponse.json({data:r.data});
    }

    if (action === 'notification.broadcast') {
      const members=await supabase.from('membership_accounts').select('id,user_id').eq('status','active').gte('level',Number(body.min_level||0)); if(members.error)throw members.error;
      const rows=(members.data||[]).map(m=>({user_id:m.user_id,membership_id:m.id,kind:body.kind||'general',title:String(body.title||''),body:String(body.message||''),action_url:body.action_url||null,status:'queued',scheduled_at:body.scheduled_at||new Date().toISOString()}));
      if(!rows.length)return NextResponse.json({data:{created:0}});
      const msgs=await supabase.from('member_notification_messages').insert(rows).select('id,user_id'); if(msgs.error)throw msgs.error;
      const channels=await supabase.from('member_contact_channels').select('id,user_id,channel_type,external_account_id').eq('is_enabled',true).eq('can_receive_notifications',true).in('user_id',(members.data||[]).map(m=>m.user_id)); if(channels.error)throw channels.error;
      const deliveries=(msgs.data||[]).flatMap(n=>(channels.data||[]).filter(c=>c.user_id===n.user_id).map(c=>({notification_id:n.id,user_id:n.user_id,channel_id:c.id,channel_type:c.channel_type,destination_masked:c.external_account_id?`***${c.external_account_id.slice(-4)}`:null,status:'queued'})));
      if(deliveries.length){const d=await supabase.from('member_notification_deliveries').insert(deliveries);if(d.error)throw d.error;}
      return NextResponse.json({data:{created:msgs.data?.length||0,deliveries:deliveries.length}});
    }

    return NextResponse.json({error:'unknown_action'},{status:400});
  } catch (e) {
    return NextResponse.json({error:e instanceof Error?e.message:'forbidden'},{status:403});
  }
}
