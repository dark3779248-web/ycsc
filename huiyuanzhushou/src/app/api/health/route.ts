import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const supabaseUrl = process.env.SUPABASE_URL;
  const publishableKey = process.env.SUPABASE_PUBLISHABLE_KEY;

  return NextResponse.json(
    {
      ok: Boolean(supabaseUrl && publishableKey),
      service: "huiyuanzhushou-h5",
      environment: process.env.VERCEL_ENV ?? process.env.NODE_ENV ?? "unknown",
      supabase: {
        urlConfigured: Boolean(supabaseUrl),
        publishableKeyConfigured: Boolean(publishableKey),
      },
      timestamp: new Date().toISOString(),
    },
    { status: supabaseUrl && publishableKey ? 200 : 503 },
  );
}
