import { createClient } from '@supabase/supabase-js';

export function createAdminSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error('Missing Supabase server environment variables');
  return createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false } });
}

export async function requireAdmin(accessToken: string) {
  const supabase = createAdminSupabase();
  const { data: userData, error: userError } = await supabase.auth.getUser(accessToken);
  if (userError || !userData.user) throw new Error('UNAUTHORIZED');

  const { data: admin, error } = await supabase
    .from('member_admin_users')
    .select('user_id,role,is_enabled,display_name')
    .eq('user_id', userData.user.id)
    .eq('is_enabled', true)
    .maybeSingle();

  if (error || !admin) throw new Error('FORBIDDEN');
  return { supabase, user: userData.user, admin };
}
