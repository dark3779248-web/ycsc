import logging
import os
from typing import Any
import httpx
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
load_dotenv(); TOKEN=os.environ['TELEGRAM_BOT_TOKEN']; URL=os.environ['SUPABASE_URL'].rstrip('/'); KEY=os.environ['SUPABASE_SERVICE_ROLE_KEY']; CATALOG=os.getenv('CATALOG_API_URL','https://huiyuanzhushou.vercel.app/api/catalog')
logging.basicConfig(level=logging.INFO); log=logging.getLogger('huiyuanzhushou-bot')
CATS=[('all','全站'),('sports','体育'),('live','真人'),('esports','电竞'),('chess','棋牌'),('slots','电子'),('entertainment','娱乐'),('lottery','彩票')]; CN=dict(CATS)
async def sb(path,params=None):
 async with httpx.AsyncClient(timeout=15) as c:
  r=await c.get(f'{URL}/rest/v1/{path}',headers={'apikey':KEY,'Authorization':f'Bearer {KEY}'},params=params); r.raise_for_status(); return r.json()
async def get_sites(): return await sb('member_sites',{'select':'id,code,name','is_enabled':'eq.true','order':'sort_order.asc,name.asc'})
async def api(params):
 async with httpx.AsyncClient(timeout=20) as c: r=await c.get(CATALOG,params=params); r.raise_for_status(); return r.json()
async def get_accounts(tid):
 ch=await sb('member_contact_channels',{'select':'user_id','channel_type':'eq.telegram','external_account_id':f'eq.{tid}','is_enabled':'eq.true','limit':'1'})
 if not ch:return []
 aa=await sb('member_site_accounts',{'select':'id,site_id,account_name,vip_level,is_starred','user_id':f"eq.{ch[0]['user_id']}",'is_enabled':'eq.true'}); sm={s['id']:s for s in await get_sites()}; return [{**a,'site':sm[a['site_id']]} for a in aa if a['site_id'] in sm]
def text(d):
 names=[v['name'] for v in d.get('venues',[]) if str(v['code']) in d.get('selected',set())]; venue='、'.join(names) if names else '不限场馆'; vip=f" · VIP{d['vip']}" if d.get('vip') is not None else ''
 return f"🔎 福利活动查询\n\n👤 账户：{d.get('account') or '临时查询'}{vip}\n🏢 站点：{d.get('site_name','请选择')}\n💰 金额：{d.get('amount',1000):,.0f}\n💳 类型：{'充值' if d.get('basis')=='deposit' else '投注'}\n🎮 分类：{CN.get(d.get('category','all'))}\n🏟 场馆：{venue}\n\n修改条件后，直接点击查询。"
def panel(d):
 mark=lambda s,on:('✓ '+s if on else s); a=d.get('amount',1000); b=d.get('basis','bet'); cat=d.get('category','all'); rows=[[InlineKeyboardButton('👤 会员账户 / 站点',callback_data='source')],[InlineKeyboardButton(mark('100',a==100),callback_data='a:100'),InlineKeyboardButton(mark('1,000',a==1000),callback_data='a:1000'),InlineKeyboardButton(mark('10,000',a==10000),callback_data='a:10000'),InlineKeyboardButton(mark('100,000',a==100000),callback_data='a:100000')],[InlineKeyboardButton('✏️ 自定义金额',callback_data='custom')],[InlineKeyboardButton(mark('投注',b=='bet'),callback_data='b:bet'),InlineKeyboardButton(mark('充值',b=='deposit'),callback_data='b:deposit')]]
 for i in range(0,8,4):rows.append([InlineKeyboardButton(mark(n,cat==v),callback_data='c:'+v) for v,n in CATS[i:i+4]])
 rows += [[InlineKeyboardButton(f"🏟 选择场馆（{len(d.get('selected',set())) or '不限'}）",callback_data='venues')],[InlineKeyboardButton('🔍 查询符合活动',callback_data='go')]]; return InlineKeyboardMarkup(rows)
def source_kb(d):
 rows=[[InlineKeyboardButton(f"⭐ {a['site']['name']} · {a.get('account_name') or '会员'} · VIP{a.get('vip_level','-')}",callback_data='acct:'+a['id'])] for a in d.get('accounts',{}).values()]; rows += [[InlineKeyboardButton('临时 · '+s['name'],callback_data='site:'+s['id'])] for s in d.get('sites',{}).values()]; rows.append([InlineKeyboardButton('⬅️ 返回',callback_data='panel')]); return InlineKeyboardMarkup(rows)
def venue_kb(d):
 vs=d.get('venues',[]); sel=d.get('selected',set()); rows=[[InlineKeyboardButton('全选',callback_data='vall'),InlineKeyboardButton('全不选',callback_data='vnone')]]
 for i in range(0,len(vs),2):rows.append([InlineKeyboardButton(('✅ ' if str(v['code']) in sel else '▫️ ')+v['name'],callback_data='v:'+str(v['code'])) for v in vs[i:i+2]])
 rows.append([InlineKeyboardButton('✅ 完成',callback_data='panel')]); return InlineKeyboardMarkup(rows)
async def load_venues(d):
 r=await api({'site_id':d['site_id'],'category':d.get('category','all'),'meta':1}); d['venues']=r.get('venues') or []; d['selected']=set()
async def show(q,d): await q.edit_message_text(text(d),reply_markup=panel(d))
async def start(u:Update,c:ContextTypes.DEFAULT_TYPE):
 c.user_data.clear(); ss=await get_sites(); aa=await get_accounts(u.effective_user.id); d=c.user_data; d.update({'sites':{x['id']:x for x in ss},'accounts':{x['id']:x for x in aa},'amount':1000,'basis':'bet','category':'all','vip':None,'selected':set()})
 if aa:a=aa[0];d.update({'site_id':a['site_id'],'site_name':a['site']['name'],'account':a.get('account_name'),'vip':a.get('vip_level')})
 elif ss:s=ss[0];d.update({'site_id':s['id'],'site_name':s['name'],'account':None})
 else:await u.effective_message.reply_text('目前还没有启用的站点。');return
 await load_venues(d);await u.effective_message.reply_text(text(d),reply_markup=panel(d))
async def callback(u:Update,c:ContextTypes.DEFAULT_TYPE):
 q=u.callback_query;await q.answer();x=q.data;d=c.user_data
 if x=='panel':await show(q,d)
 elif x=='source':await q.edit_message_text('选择会员账户或临时站点：',reply_markup=source_kb(d))
 elif x.startswith('acct:'):
  a=d['accounts'][x[5:]];d.update({'site_id':a['site_id'],'site_name':a['site']['name'],'account':a.get('account_name'),'vip':a.get('vip_level')});await load_venues(d);await show(q,d)
 elif x.startswith('site:'):
  s=d['sites'][x[5:]];d.update({'site_id':s['id'],'site_name':s['name'],'account':None,'vip':None});await load_venues(d);await show(q,d)
 elif x.startswith('a:'):d['amount']=float(x[2:]);await show(q,d)
 elif x=='custom':d['waiting']=True;await q.edit_message_text('请输入自定义金额，例如：1500')
 elif x.startswith('b:'):d['basis']=x[2:];await show(q,d)
 elif x.startswith('c:'):d['category']=x[2:];await load_venues(d);await show(q,d)
 elif x=='venues':await q.edit_message_text('选择场馆（可多选；全不选 = 不限制）：',reply_markup=venue_kb(d))
 elif x=='vall':d['selected']={str(v['code']) for v in d['venues']};await q.edit_message_reply_markup(reply_markup=venue_kb(d))
 elif x=='vnone':d['selected']=set();await q.edit_message_reply_markup(reply_markup=venue_kb(d))
 elif x.startswith('v:'):
  z=x[2:];s=set(d['selected']);s.remove(z) if z in s else s.add(z);d['selected']=s;await q.edit_message_reply_markup(reply_markup=venue_kb(d))
 elif x=='go':await query(q,d)
async def amount(u:Update,c:ContextTypes.DEFAULT_TYPE):
 if not c.user_data.get('waiting'):return
 try:n=float(u.effective_message.text.replace(',',''));assert n>0
 except:await u.effective_message.reply_text('请输入大于0的数字');return
 c.user_data['amount']=n;c.user_data['waiting']=False;await u.effective_message.reply_text(text(c.user_data),reply_markup=panel(c.user_data))
async def query(q,d):
 p={'site_id':d['site_id'],'amount':d['amount'],'amount_basis':d['basis'],'category':d['category']};
 if d.get('vip') is not None:p['vip']=d['vip']
 if d['selected']:p['venues']=','.join(d['selected'])
 r=await api(p);ps=r.get('promotions') or []
 out='没有找到符合当前条件的活动。' if not ps else '\n\n'.join([f"{i}. {x.get('title')}\n预计彩金：{float(x['estimated_bonus']):,.2f}"+(f"\n{x.get('summary')}" if x.get('summary') else '') for i,x in enumerate(ps,1)])
 await q.edit_message_text(out,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ 返回查询面板',callback_data='panel')]]))
def main():
 a=Application.builder().token(TOKEN).build();a.add_handler(CommandHandler('start',start));a.add_handler(CallbackQueryHandler(callback));a.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,amount));a.run_polling(drop_pending_updates=True)
if __name__=='__main__':main()
