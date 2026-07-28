const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!;
const storageKey = "finwise_supabase_session";

export type AppUser = { id: string; email?: string };
type Session = { access_token: string; refresh_token?: string; user: AppUser };
type Listener = (event: string, session: Session | null) => void;
const listeners = new Set<Listener>();

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
  if (!response.ok) return { data: null, error: { message: data?.msg || data?.message || data?.error_description || "请求失败" } };
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
    async signUp({ email, password, options }: { email: string; password: string; options?: { emailRedirectTo?: string } }) {
      const result = await request("/auth/v1/signup", { method: "POST", body: JSON.stringify({ email, password, data: {}, email_redirect_to: options?.emailRedirectTo }) });
      const payload = result.data as (Session & { session?: Session }) | null;
      const next = payload?.access_token ? payload as Session : payload?.session || null;
      if (next) save(next, "SIGNED_IN");
      return { data: { session: next, user: payload?.user || null }, error: result.error };
    },
    async resetPasswordForEmail(email: string, options?: { redirectTo?: string }) {
      return request("/auth/v1/recover", { method: "POST", body: JSON.stringify({ email, redirect_to: options?.redirectTo }) });
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
};
