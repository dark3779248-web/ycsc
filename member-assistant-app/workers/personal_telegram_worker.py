import asyncio,os
from datetime import datetime,timezone,timedelta
from supabase import create_client
from telethon import TelegramClient
from telethon.sessions import StringSession

URL=os.environ['NEXT_PUBLIC_SUPABASE_URL']; KEY=os.environ['SUPABASE_SERVICE_ROLE_KEY']; API_ID=int(os.environ['TELEGRAM_API_ID']); API_HASH=os.environ['TELEGRAM_API_HASH']; POLL=int(os.getenv('PERSONAL_TG_POLL_SECONDS','15'))
sb=create_client(URL,KEY); clients={}
def now(): return datetime.now(timezone.utc)
async def get_client(ref):
    if ref in clients:return clients[ref]
    session=os.environ.get(ref or '')
    if not session:raise RuntimeError(f'missing session env: {ref}')
    c=TelegramClient(StringSession(session),API_ID,API_HASH);await c.connect()
    if not await c.is_user_authorized():raise RuntimeError(f'unauthorized Telegram session: {ref}')
    clients[ref]=c;return c
async def process(row):
    n=row.get('notification') or {}; ch=row.get('channel') or {}; attempt=int(row.get('attempt_count') or 0)+1; max_attempts=int(row.get('max_attempts') or 3); ts=now().isoformat()
    sb.table('member_notification_deliveries').update({'status':'sending','attempt_count':attempt,'updated_at':ts}).eq('id',row['id']).execute()
    try:
        c=await get_client(ch.get('credential_ref')); dest=ch.get('external_account_id') or ch.get('username')
        if not dest:raise RuntimeError('personal Telegram destination missing')
        msg=await c.send_message(int(dest) if str(dest).lstrip('-').isdigit() else dest,f"{n.get('title','通知')}\n\n{n.get('body','')}")
        sb.table('member_notification_deliveries').update({'status':'delivered','provider_message_id':str(msg.id),'sent_at':ts,'delivered_at':ts,'last_error':None,'updated_at':ts}).eq('id',row['id']).execute()
    except Exception as e:
        terminal=attempt>=max_attempts; delay=[60,300,900,3600][min(attempt-1,3)]
        sb.table('member_notification_deliveries').update({'status':'failed','last_error':str(e)[:1000],'failed_at':ts,'terminal_failure':terminal,'next_attempt_at':(now()+timedelta(seconds=delay)).isoformat(),'updated_at':ts}).eq('id',row['id']).execute()
        if terminal:
            sb.table('member_notification_deliveries').insert({'notification_id':row['notification_id'],'user_id':row['user_id'],'channel_type':'h5','status':'delivered','fallback_from_delivery_id':row['id'],'queued_at':ts,'sent_at':ts,'delivered_at':ts,'metadata':{'fallback_reason':'personal_telegram_failed'}}).execute()
async def loop():
    while True:
        try:
            r=sb.table('member_notification_deliveries').select('id,notification_id,user_id,channel_id,attempt_count,max_attempts,notification:member_notification_messages(title,body),channel:member_contact_channels(external_account_id,username,credential_ref)').eq('channel_type','personal_telegram').in_('status',['queued','failed']).eq('terminal_failure',False).lte('next_attempt_at',now().isoformat()).limit(20).execute()
            for row in r.data or []:await process(row)
        except Exception as e:print('personal telegram worker error:',e,flush=True)
        await asyncio.sleep(POLL)
if __name__=='__main__':asyncio.run(loop())
