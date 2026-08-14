import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn(
    "Supabase is not configured (missing VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY) " +
    "— registry lookups in onboarding will fail until frontend/.env is set."
  );
}

export const supabase = createClient(supabaseUrl ?? "", supabaseAnonKey ?? "", {
  db: { schema: "penta_document_registries" },
});