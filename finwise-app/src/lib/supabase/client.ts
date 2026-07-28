const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!;
const storageKey = "finwise_supabase_session";

export type AppUser = { id: string; email?: string };
export type AppPosition = {
  user_id: string; market_id: string; side: "yes" | "no"; shares: number; cost_basis: number; updated_at: string;
  markets: { title: string; status: "open" | "closed" | "settled" | "cancelled"; outcome: "yes" | "no" | null; yes_price: number; no_price: number };
};
type Session = { access_token: string; refresh_token?: string; user: AppUser };
type Listener = (event: string, session: Session | null) => void;
const listeners = new Set<Listener>();

function translateError(message: string) {
  const wait = message.match(/For security purposes, you can only request this after (\d+) seconds?\.?/i);
  if (wait) return `为保障账户安全，请在 ${wait[1]} 秒后重试。`;
  const translations: Array<[RegExp, string]> = [
    [/email rate limit exceeded/i, "邮件发送过于频繁，请稍后重试。"],
    [/user already registered/i, "该邮箱已经注册，请直接登录。"],
    [/invalid login credentials/i, "邮箱或密码错误。"],
    [/email not confirmed/i, "邮箱尚未验证，请先查看确认邮件。"],
    [/password should be at least/i, "密码长度未达到安全要求。"],
    [/signup is disabled/i, "当前暂未开放注册。"],
    [/AUTH_REQUIRED/i, "请先登录后再进行预测。"],
    [/MIN_AMOUNT/i, "单笔预测金额不能低于 1 USDT。"],
    [/MARKET_NOT_FOUND/i, "未找到该预测市场。"],
    [/MARKET_CLOSED/i, "该市场已经停止预测。"],
    [/INSUFFICIENT_BALANCE/i, "账户余额不足，请减少预测金额。"],
  ];
  return translations.find(([pattern]) => pattern.test(message))?.[1] || "操作失败，请稍后重试。";
}

function session(): Session | null {
  if (typeof window === "undefined") return null;
  try { return JSON.parse(localStorage.getItem(storageKey) || "null"); } catch { return null; }
}

async function request(path: string, init: RequestInit = {}, authenticated = false) {
  const token = authenticated ? session()?.access_token : undefined;
  const response = await fetch(`${url}${path}`, {
    ...init,
    headers: { apikey: key, "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers },
  });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const message = data?.msg || data?.message || data?.error_description || "请求失败";
    return { data: null, error: { message: translateError(message) } };
  }
  return { data, error: null };
}

function save(next: Session | null, event: string) {
  if (next) localStorage.setItem(storageKey, JSON.stringify(next)); else localStorage.removeItem(storageKey);
  listeners.forEach((listener) => listener(event, next));
}

export const supabase = {
  auth: {
    async getUser() {
      const current = session();
      if (!current) return { data: { user: null }, error: null };
      const result = await request("/auth/v1/user", {}, true);
      if (result.error) { save(null, "SIGNED_OUT"); return { data: { user: null }, error: result.error }; }
      return { data: { user: result.data as AppUser }, error: null };
    },
    onAuthStateChange(listener: Listener) {
      listeners.add(listener);
      return { data: { subscription: { unsubscribe: () => { listeners.delete(listener); } } } };
    },
    async signInWithPassword(credentials: { email: string; password: string }) {
      const result = await request("/auth/v1/token?grant_type=password", { method: "POST", body: JSON.stringify(credentials) });
      if (!result.error) save(result.data as Session, "SIGNED_IN");
      return result;
    },
    async signUp({ email, password, options }: { email: string; password: string; options?: { emailRedirectTo?: string; displayName?: string } }) {
      const result = await request("/auth/v1/signup", { method: "POST", body: JSON.stringify({ email, password, data: { display_name: options?.displayName }, email_redirect_to: options?.emailRedirectTo }) });
      const payload = result.data as (Session & { session?: Session }) | null;
      const next = payload?.access_token ? payload as Session : payload?.session || null;
      if (next) save(next, "SIGNED_IN");
      return { data: { session: next, user: payload?.user || null }, error: result.error };
    },
    async resetPasswordForEmail(email: string, options?: { redirectTo?: string }) {
      return request("/auth/v1/recover", { method: "POST", body: JSON.stringify({ email, redirect_to: options?.redirectTo }) });
    },
    async signInWithOtp(email: string, options?: { redirectTo?: string }) {
      const redirect = options?.redirectTo ? `?redirect_to=${encodeURIComponent(options.redirectTo)}` : "";
      return request(`/auth/v1/otp${redirect}`, { method: "POST", body: JSON.stringify({ email, create_user: true }) });
    },
    async resendSignup(email: string) {
      return request("/auth/v1/resend", { method: "POST", body: JSON.stringify({ type: "signup", email }) });
    },
    async signOut() {
      await request("/auth/v1/logout", { method: "POST" }, true);
      save(null, "SIGNED_OUT");
      return { error: null };
    },
  },
  from(table: string) {
    let fields = "*"; let filter = "";
    const query = {
      select(value: string) { fields = value; return query; },
      eq(column: string, value: string) { filter = `&${encodeURIComponent(column)}=eq.${encodeURIComponent(value)}`; return query; },
      async single() {
        const result = await request(`/rest/v1/${encodeURIComponent(table)}?select=${encodeURIComponent(fields)}${filter}`, { headers: { Accept: "application/vnd.pgrst.object+json" } }, true);
        return result;
      },
    };
    return query;
  },
  async placeOrder(input: { marketSlug: string; side: "yes" | "no"; amount: number }) {
    const result = await request("/rest/v1/rpc/place_order", { method: "POST", body: JSON.stringify({ p_market_slug: input.marketSlug, p_side: input.side, p_amount: input.amount }) }, true);
    return result as { data: { order_id: string; balance: number; shares: number; price: number } | null; error: { message: string } | null };
  },
  async getPositions() {
    const select = "user_id,market_id,side,shares,cost_basis,updated_at,markets(title,status,outcome,yes_price,no_price)";
    const result = await request(`/rest/v1/positions?select=${encodeURIComponent(select)}&order=updated_at.desc`, {}, true);
    return result as { data: AppPosition[] | null; error: { message: string } | null };
  },
};
