import { NextRequest, NextResponse } from 'next/server';

const url = process.env.SUPABASE_URL;
const key = process.env.SUPABASE_PUBLISHABLE_KEY;

async function sb(path: string) {
  if (!url || !key) throw new Error('Missing Supabase environment variables');
  const res = await fetch(`${url}/rest/v1/${path}`, {
    headers: {
      apikey: key,
      Authorization: `Bearer ${key}`,
    },
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const siteId = searchParams.get('site_id');
    const category = searchParams.get('category') || 'all';
    const amount = Number(searchParams.get('amount') || 0);
    const amountBasis = searchParams.get('amount_basis') === 'deposit' ? 'deposit' : 'bet';
    const vipParam = searchParams.get('vip');
    const vip = vipParam === null || vipParam === '' ? null : Number(vipParam);
    const metaOnly = searchParams.get('meta') === '1';
    const selectedVenues = (searchParams.get('venues') || '')
      .split(',')
      .map(v => v.trim())
      .filter(Boolean);

    const sites = await sb('member_sites?select=id,code,name&is_enabled=eq.true&order=sort_order.asc,name.asc');
    if (!siteId) return NextResponse.json({ sites, venues: [], promotions: [] });

    const venueCategoryFilter = category === 'all' ? '' : `&category=in.(all,${encodeURIComponent(category)})`;
    const venues = await sb(`member_venues?select=id,site_id,category,code,name&site_id=eq.${encodeURIComponent(siteId)}&is_enabled=eq.true${venueCategoryFilter}&order=sort_order.asc,name.asc`);

    if (metaOnly) return NextResponse.json({ sites, venues, promotions: [] });

    const promotions = await sb(`member_promotions?select=id,title,summary,image_url,frontend_url,application_method,turnover_multiple,max_bonus,current_version&site_id=eq.${encodeURIComponent(siteId)}&status=eq.active&order=sort_order.asc,title.asc`);
    if (!promotions.length) return NextResponse.json({ sites, venues, promotions: [] });

    const ids = promotions.map((p: { id: string }) => p.id).join(',');
    const rules = await sb(`member_promotion_rules?select=promotion_id,category,min_amount,max_amount,amount_basis,bonus_type,bonus_value,bonus_cap,vip_min,vip_max,venue_codes,rule_json&promotion_id=in.(${ids})&is_enabled=eq.true`);

    const matched = promotions.flatMap((promotion: Record<string, unknown>) => {
      const promotionRules = rules.filter((rule: { promotion_id: string; category: string; min_amount: number | null; max_amount: number | null; amount_basis?: string; vip_min?: number | null; vip_max?: number | null; venue_codes?: unknown }) => {
        if (rule.promotion_id !== promotion.id) return false;
        if ((rule.amount_basis || 'bet') !== amountBasis) return false;
        if (category !== 'all' && rule.category !== 'all' && rule.category !== category) return false;
        if (rule.min_amount !== null && amount < Number(rule.min_amount)) return false;
        if (rule.max_amount !== null && amount > Number(rule.max_amount)) return false;
        if (vip !== null && Number.isFinite(vip)) {
          if (rule.vip_min !== null && rule.vip_min !== undefined && vip < Number(rule.vip_min)) return false;
          if (rule.vip_max !== null && rule.vip_max !== undefined && vip > Number(rule.vip_max)) return false;
        }

        const ruleVenues = Array.isArray(rule.venue_codes)
          ? rule.venue_codes.map(String)
          : [];
        if (selectedVenues.length && ruleVenues.length && !selectedVenues.some(v => ruleVenues.includes(v))) return false;
        return true;
      });

      return promotionRules.map((rule: { amount_basis?: string; bonus_type: string; bonus_value: number | null; bonus_cap: number | null; vip_min?: number | null; vip_max?: number | null; venue_codes: unknown; rule_json: unknown }) => {
        let estimatedBonus: number | null = null;
        if (rule.bonus_type === 'fixed') estimatedBonus = Number(rule.bonus_value || 0);
        if (rule.bonus_type === 'percent') estimatedBonus = amount * Number(rule.bonus_value || 0) / 100;
        if (estimatedBonus !== null && rule.bonus_cap !== null) estimatedBonus = Math.min(estimatedBonus, Number(rule.bonus_cap));
        return { ...promotion, ...rule, amount_basis: rule.amount_basis || 'bet', estimated_bonus: estimatedBonus };
      });
    });

    return NextResponse.json({ sites, venues, amount_basis: amountBasis, vip, promotions: matched });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : 'Unknown error' }, { status: 500 });
  }
}
