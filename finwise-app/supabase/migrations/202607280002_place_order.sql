-- Atomic virtual-credit order placement for the FinWise MVP.
create or replace function public.place_order(
  p_market_slug text,
  p_side public.order_side,
  p_amount numeric
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_market public.markets%rowtype;
  v_profile public.profiles%rowtype;
  v_price numeric(5,4);
  v_shares numeric(18,6);
  v_balance numeric(18,2);
  v_order_id uuid;
begin
  if v_user_id is null then raise exception 'AUTH_REQUIRED'; end if;
  if p_amount is null or p_amount < 1 then raise exception 'MIN_AMOUNT'; end if;

  select * into v_market from public.markets where slug = p_market_slug for update;
  if not found then raise exception 'MARKET_NOT_FOUND'; end if;
  if v_market.status <> 'open' or v_market.closes_at <= now() then raise exception 'MARKET_CLOSED'; end if;

  select * into v_profile from public.profiles where id = v_user_id for update;
  if not found then raise exception 'PROFILE_NOT_FOUND'; end if;
  if v_profile.virtual_balance < p_amount then raise exception 'INSUFFICIENT_BALANCE'; end if;

  v_price := case when p_side = 'yes' then v_market.yes_price else v_market.no_price end;
  v_shares := round(p_amount / v_price, 6);
  v_balance := round(v_profile.virtual_balance - p_amount, 2);

  insert into public.orders(user_id, market_id, side, amount, price, shares)
  values(v_user_id, v_market.id, p_side, p_amount, v_price, v_shares)
  returning id into v_order_id;

  insert into public.positions(user_id, market_id, side, shares, cost_basis)
  values(v_user_id, v_market.id, p_side, v_shares, p_amount)
  on conflict(user_id, market_id, side) do update
  set shares = public.positions.shares + excluded.shares,
      cost_basis = public.positions.cost_basis + excluded.cost_basis,
      updated_at = now();

  update public.profiles set virtual_balance = v_balance, updated_at = now() where id = v_user_id;
  insert into public.ledger_entries(user_id, kind, amount, balance_after, reference_id, note)
  values(v_user_id, 'trade_debit', -p_amount, v_balance, v_order_id, v_market.title);

  return jsonb_build_object('order_id',v_order_id,'balance',v_balance,'shares',v_shares,'price',v_price);
end;
$$;

revoke all on function public.place_order(text, public.order_side, numeric) from public;
grant execute on function public.place_order(text, public.order_side, numeric) to authenticated;
