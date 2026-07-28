-- Promote the designated operator and expose audited market-management RPCs.
do $$
declare v_id uuid;
begin
  select id into v_id from auth.users where lower(email)=lower('gff11234@gmail.com');
  if v_id is null then raise exception 'ADMIN_ACCOUNT_NOT_FOUND'; end if;
  update public.profiles set role='admin', updated_at=now() where id=v_id;
end $$;

create or replace function public.assert_admin()
returns void language plpgsql security definer set search_path=public as $$
begin
  if not exists(select 1 from public.profiles where id=auth.uid() and role='admin') then
    raise exception 'ADMIN_REQUIRED';
  end if;
end; $$;

create or replace function public.admin_list_markets()
returns setof public.markets language plpgsql security definer set search_path=public as $$
begin
  perform public.assert_admin();
  return query select * from public.markets order by created_at desc;
end; $$;

create or replace function public.admin_create_market(
  p_title text, p_slug text, p_category text, p_description text,
  p_resolution_rules text, p_yes_price numeric, p_closes_at timestamptz
)
returns public.markets language plpgsql security definer set search_path=public as $$
declare v_market public.markets;
begin
  perform public.assert_admin();
  if length(trim(p_title))<5 then raise exception 'INVALID_TITLE'; end if;
  if p_yes_price<=0 or p_yes_price>=1 then raise exception 'INVALID_PRICE'; end if;
  if p_closes_at<=now() then raise exception 'INVALID_CLOSE_TIME'; end if;
  insert into public.markets(slug,title,description,category,resolution_rules,yes_price,status,closes_at,created_by)
  values(lower(trim(p_slug)),trim(p_title),p_description,trim(p_category),trim(p_resolution_rules),p_yes_price,'open',p_closes_at,auth.uid())
  returning * into v_market;
  insert into public.admin_audit_logs(actor_id,action,entity_type,entity_id,metadata)
  values(auth.uid(),'create','market',v_market.id::text,jsonb_build_object('title',v_market.title));
  return v_market;
end; $$;

create or replace function public.admin_set_market_status(p_market_id uuid,p_status public.market_status)
returns public.markets language plpgsql security definer set search_path=public as $$
declare v_market public.markets;
begin
  perform public.assert_admin();
  if p_status='settled' then raise exception 'USE_SETTLEMENT_FLOW'; end if;
  update public.markets set status=p_status,updated_at=now() where id=p_market_id returning * into v_market;
  if v_market.id is null then raise exception 'MARKET_NOT_FOUND'; end if;
  insert into public.admin_audit_logs(actor_id,action,entity_type,entity_id,metadata)
  values(auth.uid(),'status_change','market',v_market.id::text,jsonb_build_object('status',p_status));
  return v_market;
end; $$;

create or replace function public.admin_delete_market(p_market_id uuid)
returns boolean language plpgsql security definer set search_path=public as $$
declare v_title text;
begin
  perform public.assert_admin();
  if exists(select 1 from public.orders where market_id=p_market_id) then raise exception 'MARKET_HAS_ORDERS'; end if;
  delete from public.markets where id=p_market_id returning title into v_title;
  if v_title is null then raise exception 'MARKET_NOT_FOUND'; end if;
  insert into public.admin_audit_logs(actor_id,action,entity_type,entity_id,metadata)
  values(auth.uid(),'delete','market',p_market_id::text,jsonb_build_object('title',v_title));
  return true;
end; $$;

revoke all on function public.assert_admin() from public;
revoke all on function public.admin_list_markets() from public;
revoke all on function public.admin_create_market(text,text,text,text,text,numeric,timestamptz) from public;
revoke all on function public.admin_set_market_status(uuid,public.market_status) from public;
revoke all on function public.admin_delete_market(uuid) from public;
grant execute on function public.admin_list_markets() to authenticated;
grant execute on function public.admin_create_market(text,text,text,text,text,numeric,timestamptz) to authenticated;
grant execute on function public.admin_set_market_status(uuid,public.market_status) to authenticated;
grant execute on function public.admin_delete_market(uuid) to authenticated;
