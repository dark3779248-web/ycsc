import {createHash,randomInt} from 'crypto';
import {NextRequest,NextResponse} from 'next/server';
import {createAdminSupabase} from '@/lib/supabase/admin';

export const runtime='nodejs';
const loginRe=/^[A-Za-z][A-Za-z0-9_]{5,31}$/;
function memberNo(length:number){let out=String(randomInt(1,10));for(let i=1;i<length;i++)out+=String(randomInt(0,10));return out;}
function clientIp(req:NextRequest){return (req.headers.get('x-forwarded-for')||'unknown').split(',')[0].trim();}

export async function POST(req:NextRequest){
 const s=createAdminSupabase();let attemptId:number|null=null;let authUserId:string|null=null;
 try{
  const body=await req.json();const loginName=String(body.login_name||'').trim();const password=String(body.password||'');
  if(!loginRe.test(loginName))return NextResponse.json({error:'账号必须以英文字母开头，总长度 6-32 位，只能使用字母、数字或下划线'},{status:400});
  if(password.length<6)return NextResponse.json({error:'密码至少 6 位，并区分大小写'},{status:400});
  const salt=process.env.REGISTRATION_RATE_LIMIT_SALT||process.env.SUPABASE_SERVICE_ROLE_KEY||'member-assistant';
  const ipHash=createHash('sha256').update(`${salt}:${clientIp(req)}`).digest('hex');const since=new Date(Date.now()-60*60*1000).toISOString();
  const {count}=await s.from('h5_registration_attempts').select('*',{count:'exact',head:true}).eq('ip_hash',ipHash).gte('created_at',since);
  if((count||0)>=20)return NextResponse.json({error:'注册尝试过于频繁，请稍后再试'},{status:429});
  const a=await s.from('h5_registration_attempts').insert({ip_hash:ipHash,login_name:loginName,was_successful:false}).select('id').single();attemptId=a.data?.id??null;
  const exists=await s.from('membership_accounts').select('id').ilike('login_name',loginName).maybeSingle();if(exists.data)return NextResponse.json({error:'这个账号已被使用'},{status:409});
  const internalEmail=`${loginName.toLowerCase()}@members.invalid`;
  const created=await s.auth.admin.createUser({email:internalEmail,password,email_confirm:true,user_metadata:{source:'h5',login_name:loginName}});
  if(created.error||!created.data.user)throw created.error||new Error('创建登录账户失败');authUserId=created.data.user.id;
  const length=Math.max(9,Math.min(32,Number(process.env.MEMBER_NUMBER_LENGTH||9)||9));let inserted:any=null;
  for(let i=0;i<25;i++){
   const no=memberNo(length);const r=await s.from('membership_accounts').insert({user_id:authUserId,login_name:loginName,account_name:loginName,member_no:no,status:'active',level:0,metadata:{registration_source:'h5'}}).select('id,member_no,login_name').single();
   if(!r.error){inserted=r.data;break;}if(r.error.code!=='23505')throw r.error;
  }
  if(!inserted)throw new Error('生成唯一会员编号失败，请重试');
  if(attemptId)await s.from('h5_registration_attempts').update({was_successful:true}).eq('id',attemptId);
  return NextResponse.json({data:inserted});
 }catch(e){if(authUserId)await s.auth.admin.deleteUser(authUserId);return NextResponse.json({error:e instanceof Error?e.message:'注册失败'},{status:500});}
}
