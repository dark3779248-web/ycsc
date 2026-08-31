import { NextRequest,NextResponse } from 'next/server';
import { createAdminSupabase } from '@/lib/supabase/admin';

async function send(chatId:number,text:string,extra:Record<string,unknown>={}){
  const token=process.env.TELEGRAM_BOT_TOKEN;if(!token)return;
  await fetch(`https://api.telegram.org/bot${token}/sendMessage`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({chat_id:chatId,text,...extra})});
}

export async function POST(req:NextRequest){
  const secret=process.env.TELEGRAM_WEBHOOK_SECRET;
  if(secret&&req.headers.get('x-telegram-bot-api-secret-token')!==secret)return NextResponse.json({ok:false},{status:401});
  const update=await req.json();const m=update?.message;const chatId=m?.chat?.id;const tgUserId=m?.from?.id?.toString();const username=m?.from?.username||null;const text=(m?.text||'').trim();
  if(!chatId||!tgUserId)return NextResponse.json({ok:true});
  const s=createAdminSupabase();

  if(text==='/start'){
    await send(chatId,'欢迎使用会员权益助手。请先绑定会员账户，然后即可查看权益、通知和联系客服。',{reply_markup:{inline_keyboard:[[ {text:'打开会员中心',web_app:{url:process.env.NEXT_PUBLIC_APP_URL||'https://example.com'}} ]]}});
    return NextResponse.json({ok:true});
  }

  if(text.startsWith('/bind ')){
    const code=text.slice(6).trim().toUpperCase();
    const now=new Date().toISOString();
    const {data:b}=await s.from('telegram_binding_codes').select('id,user_id,membership_id,expires_at,used_at').eq('code',code).maybeSingle();
    if(!b||b.used_at||b.expires_at<=now){await send(chatId,'绑定码无效或已过期，请回会员中心重新生成。');return NextResponse.json({ok:true});}
    await s.from('member_contact_channels').upsert({user_id:b.user_id,membership_id:b.membership_id,channel_type:'telegram_bot',label:'Telegram Bot',external_account_id:tgUserId,username,is_enabled:true,is_primary:true,can_receive_notifications:true,can_receive_support:true,verified_at:now,last_seen_at:now},{onConflict:'user_id,channel_type,external_account_id'});
    await s.from('telegram_binding_codes').update({used_at:now}).eq('id',b.id);
    await send(chatId,'绑定成功。现在可以使用 /benefits 查看权益，或 /support 你的问题 联系客服。');
    return NextResponse.json({ok:true});
  }

  const {data:channel}=await s.from('member_contact_channels').select('id,user_id,membership_id').eq('channel_type','telegram_bot').eq('external_account_id',tgUserId).eq('is_enabled',true).maybeSingle();
  if(!channel){await send(chatId,'当前 Telegram 尚未绑定会员账户。请先在会员中心生成绑定码，再发送 /bind 绑定码。');return NextResponse.json({ok:true});}
  await s.from('member_contact_channels').update({last_seen_at:new Date().toISOString(),username}).eq('id',channel.id);

  if(text==='/benefits'){
    const {data:b}=await s.from('member_benefit_assignments').select('status,quota,used_count,expires_at,benefit:member_benefits(title)').eq('user_id',channel.user_id).eq('status','active');
    const lines=(b||[]).map((x:any)=>{const left=x.quota==null?'':`（剩余 ${Math.max(0,(x.quota||0)-(x.used_count||0))} 次）`;return `• ${x.benefit?.title||'会员权益'}${left}`});
    await send(chatId,lines.length?`当前权益：\n${lines.join('\n')}`:'当前暂无可用权益。');return NextResponse.json({ok:true});
  }

  if(text.startsWith('/support')){
    const body=text.replace('/support','').trim();if(!body){await send(chatId,'请使用 /support 你的问题');return NextResponse.json({ok:true});}
    let {data:c}=await s.from('support_conversations').select('id').eq('user_id',channel.user_id).in('status',['open','pending']).order('created_at',{ascending:false}).limit(1).maybeSingle();
    if(!c){const {data:n}=await s.from('support_conversations').insert({user_id:channel.user_id,membership_id:channel.membership_id,source_channel_id:channel.id,subject:'Telegram 会员咨询',status:'open',priority:'normal',last_message_at:new Date().toISOString()}).select('id').single();c=n;}
    if(c){await s.from('support_messages').insert({conversation_id:c.id,user_id:channel.user_id,sender_user_id:channel.user_id,sender_role:'member',source_channel_id:channel.id,body,content_type:'text',metadata:{telegram_message_id:m.message_id}});await s.from('support_conversations').update({last_message_at:new Date().toISOString(),status:'open'}).eq('id',c.id);}
    await send(chatId,'已收到，你的问题已进入客服队列。');return NextResponse.json({ok:true});
  }

  await send(chatId,'可用命令：\n/bind 绑定码  绑定会员账户\n/benefits 查看权益\n/support 你的问题  联系客服');return NextResponse.json({ok:true});
}
