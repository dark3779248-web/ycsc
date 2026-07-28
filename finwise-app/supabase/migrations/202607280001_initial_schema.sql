-- FinWise MVP: real accounts and durable prediction-market data.
-- Balances are virtual credits only. No blockchain deposits or withdrawals.

create extension if not exists pgcrypto;

create type public.market_status as enum ('draft', 'open', 'closed', 'settled', 'cancelled');
create type public.order_side as enum ('yes', 'no');
create type public.order_status as enum ('filled', 'cancelled');
create type public.ledger_kind as enum ('welcome_bonus', 'trade_debit', 'settlement_credit', 'admin_adjustment');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  avatar_url text,
  role text not null default 'user' check (role in ('user', 'admin')),
  virtual_balance numeric(18,2) not null default 10 check (virtual_balance >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.markets (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  title text not null,
  description text,
  category text not null,
  resolution_rules text not null,
  yes_price numeric(5,4) not null default .5 check (yes_price > 0 and yes_price < 1),
  no_price numeric(5,4) generated always as (1 - yes_price) stored,
  status public.market_status not null default 'draft',
  closes_at timestamptz not null,
  outcome public.order_side,
  created_by uuid references public.profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.orders (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  market_id uuid not null references public.markets(id) on delete restrict,
  side public.order_side not null,
  amount numeric(18,2) not null check (amount > 0),
  price numeric(5,4) not null check (price > 0 and price < 1),
  shares numeric(18,6) not null check (shares > 0),
  status public.order_status not null default 'filled',
  created_at timestamptz not null default now()
);

create table public.positions (
  user_id uuid not null references public.profiles(id) on delete cascade,
  market_id uuid not null references public.markets(id) on delete cascade,
  side public.order_side not null,
  shares numeric(18,6) not null default 0 check (shares >= 0),
  cost_basis numeric(18,2) not null default 0 check (cost_basis >= 0),
  updated_at timestamptz not null default now(),
  primary key (user_id, market_id, side)
);

create table public.ledger_entries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  kind public.ledger_kind not null,
  amount numeric(18,2) not null,
  balance_after numeric(18,2) not null check (balance_after >= 0),
  reference_id uuid,
  note text,
  created_at timestamptz not null default now()
);

create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  title text not null,
  body text not null,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.admin_audit_logs (
  id bigint generated always as identity primary key,
  actor_id uuid references public.profiles(id),
  action text not null,
  entity_type text not null,
  entity_id text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'display_name', split_part(new.email, '@', 1)));
  insert into public.ledger_entries (user_id, kind, amount, balance_after, note)
  values (new.id, 'welcome_bonus', 10, 10, 'FinWise MVP welcome credits');
  return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users for each row execute procedure public.handle_new_user();

alter table public.profiles enable row level security;
alter table public.markets enable row level security;
alter table public.orders enable row level security;
alter table public.positions enable row level security;
alter table public.ledger_entries enable row level security;
alter table public.notifications enable row level security;
alter table public.admin_audit_logs enable row level security;

create policy "profiles are self readable" on public.profiles for select using (auth.uid() = id);
create policy "profiles are self editable" on public.profiles for update using (auth.uid() = id) with check (auth.uid() = id and role = 'user');
create policy "open markets are public" on public.markets for select using (status in ('open', 'closed', 'settled'));
create policy "orders are private" on public.orders for select using (auth.uid() = user_id);
create policy "positions are private" on public.positions for select using (auth.uid() = user_id);
create policy "ledger is private" on public.ledger_entries for select using (auth.uid() = user_id);
create policy "notifications are private" on public.notifications for select using (auth.uid() = user_id);
create policy "notifications are self editable" on public.notifications for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create index orders_user_created_idx on public.orders(user_id, created_at desc);
create index positions_user_idx on public.positions(user_id);
create index ledger_user_created_idx on public.ledger_entries(user_id, created_at desc);
create index notifications_user_created_idx on public.notifications(user_id, created_at desc);
create index markets_status_closes_idx on public.markets(status, closes_at);

insert into public.markets (slug, title, description, category, resolution_rules, yes_price, status, closes_at)
values
('btc-100k-august', 'BTC 是否会在 8 月突破 10 万美元?', '模拟市场，仅使用虚拟积分。', '虚拟币', '若指定公开指数在截止前达到或超过 100,000 美元，则结算为 YES。', .64, 'open', '2026-08-31 23:59:00+00'),
('solana-etf-next-month', '美国 SEC 是否会在下月批准 Solana 现货 ETF?', '模拟市场，仅使用虚拟积分。', '虚拟币', '以监管机构公开公告为最终依据。', .55, 'open', '2026-08-31 23:59:00+00'),
('england-next-world-cup', '英格兰队能否夺得下一届世界杯冠军?', '模拟市场，仅使用虚拟积分。', '体育', '以赛事官方最终冠军结果为依据。', .38, 'open', '2026-09-30 23:59:00+00');
