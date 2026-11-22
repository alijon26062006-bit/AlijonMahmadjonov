import { createClient, SupabaseClient } from "jsr:@supabase/supabase-js@2";

export const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-hook-secret",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}

export function adminClient(): SupabaseClient {
  return createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false, autoRefreshToken: false } },
  );
}

/// Calls come from the database (x-hook-secret) only.
export async function isHook(req: Request, admin: SupabaseClient): Promise<boolean> {
  const secret = req.headers.get("x-hook-secret") ?? "";
  if (secret.length < 32) return false;
  const { data } = await admin.rpc("hook_secret_ok", { p_secret: secret });
  return data === true;
}

export async function setAiStatus(admin: SupabaseClient, configured: boolean, error?: string) {
  await admin.from("app_settings").upsert({
    key: "ai_status",
    value: { ai_configured: configured, last_error: error ?? null, at: new Date().toISOString() },
    updated_at: new Date().toISOString(),
  });
}
