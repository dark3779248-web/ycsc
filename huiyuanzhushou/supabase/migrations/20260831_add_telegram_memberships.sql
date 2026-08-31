alter table public.membership_accounts
  alter column user_id drop not null;

alter table public.member_contact_channels
  alter column user_id drop not null;

alter table public.member_site_accounts
  alter column user_id drop not null;

alter table public.membership_accounts
  add column if not exists telegram_user_id bigint;

create unique index if not exists membership_accounts_telegram_user_id_key
  on public.membership_accounts (telegram_user_id)
  where telegram_user_id is not null;

create unique index if not exists member_contact_channels_telegram_external_key
  on public.member_contact_channels (channel_type, external_account_id)
  where channel_type in ('telegram_bot', 'personal_telegram', 'main_bot', 'backup_bot')
    and external_account_id is not null
    and is_enabled;

alter table public.membership_accounts
  drop constraint if exists membership_accounts_has_identity;
alter table public.membership_accounts
  add constraint membership_accounts_has_identity
  check (user_id is not null or telegram_user_id is not null);

alter table public.member_contact_channels
  drop constraint if exists member_contact_channels_has_owner;
alter table public.member_contact_channels
  add constraint member_contact_channels_has_owner
  check (user_id is not null or membership_id is not null);

alter table public.member_site_accounts
  drop constraint if exists member_site_accounts_has_owner;
alter table public.member_site_accounts
  add constraint member_site_accounts_has_owner
  check (user_id is not null or membership_id is not null);

create or replace function public.get_or_create_telegram_membership(
  p_telegram_id bigint,
  p_display_name text default null,
  p_username text default null
)
returns table (membership_id uuid)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_membership_id uuid;
begin
  select c.membership_id
    into v_membership_id
    from public.member_contact_channels c
   where c.channel_type in ('telegram_bot', 'personal_telegram', 'main_bot', 'backup_bot')
     and c.external_account_id = p_telegram_id::text
     and c.is_enabled
     and c.membership_id is not null
   order by c.is_primary desc, c.created_at asc
   limit 1;

  if v_membership_id is not null then
    return query select v_membership_id;
    return;
  end if;

  insert into public.membership_accounts (
    account_name,
    telegram_user_id,
    metadata
  ) values (
    coalesce(nullif(trim(p_display_name), ''), 'Telegram ' || p_telegram_id::text),
    p_telegram_id,
    jsonb_build_object('source', 'telegram_bot')
  )
  on conflict (telegram_user_id) where telegram_user_id is not null
  do update set
    account_name = coalesce(nullif(trim(excluded.account_name), ''), public.membership_accounts.account_name),
    updated_at = now()
  returning id into v_membership_id;

  insert into public.member_contact_channels (
    membership_id,
    channel_type,
    label,
    external_account_id,
    username,
    is_primary,
    verified_at,
    metadata
  ) values (
    v_membership_id,
    'telegram_bot',
    'Telegram Bot',
    p_telegram_id::text,
    nullif(trim(p_username), ''),
    true,
    now(),
    jsonb_build_object('source', 'telegram_bot')
  )
  on conflict (channel_type, external_account_id)
    where channel_type in ('telegram_bot', 'personal_telegram', 'main_bot', 'backup_bot')
      and external_account_id is not null
      and is_enabled
  do update set
    membership_id = excluded.membership_id,
    username = excluded.username,
    updated_at = now();

  return query select v_membership_id;
end;
$$;

revoke all on function public.get_or_create_telegram_membership(bigint, text, text)
  from public, anon, authenticated;
grant execute on function public.get_or_create_telegram_membership(bigint, text, text)
  to service_role;
