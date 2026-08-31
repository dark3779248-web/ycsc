import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const supabaseUrl = process.env.SUPABASE_URL;
  const publishableKey = process.env.SUPABASE_PUBLISHABLE_KEY;
  const validSupabaseUrl = Boolean(
    supabaseUrl && /^https:\/\/[a-z0-9-]+\.supabase\.co\/?$/i.test(supabaseUrl),
  );

  const ok = Boolean(validSupabaseUrl && publishableKey);

  return NextResponse.json(
    {
      ok,
      service: "huiyuanzhushou-h5",
      environment: process.env.VERCEL_ENV ?? process.env.NODE_ENV ?? "unknown",
      supabase: {
        urlConfigured: Boolean(supabaseUrl),
        urlValid: validSupabaseUrl,
        publishableKeyConfigured: Boolean(publishableKey),
      },
      timestamp: new Date().toISOString(),
    },
    { status: ok ? 200 : 503 },
  );
}
