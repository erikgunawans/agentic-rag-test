-- Migration 008: RBAC Settings Architecture
-- Decouples system config (admin-only) from user preferences (per-user)

-- ============================================================
-- 1. System Settings (single-row, admin-only)
-- ============================================================
CREATE TABLE IF NOT EXISTS system_settings (
  id integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  llm_model text NOT NULL DEFAULT 'openai/gpt-4o-mini',
  embedding_model text NOT NULL DEFAULT 'text-embedding-3-small',
  rag_top_k integer NOT NULL DEFAULT 5,
  rag_similarity_threshold real NOT NULL DEFAULT 0.3,
  rag_chunk_size integer NOT NULL DEFAULT 500,
  rag_chunk_overlap integer NOT NULL DEFAULT 50,
  rag_hybrid_enabled boolean NOT NULL DEFAULT true,
  rag_rrf_k integer NOT NULL DEFAULT 60,
  tools_enabled boolean NOT NULL DEFAULT true,
  tools_max_iterations integer NOT NULL DEFAULT 5,
  agents_enabled boolean NOT NULL DEFAULT false,
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Seed the single row
INSERT INTO system_settings (id) VALUES (1) ON CONFLICT DO NOTHING;

-- Helper: check if current JWT user is super_admin
CREATE OR REPLACE FUNCTION is_super_admin()
RETURNS boolean AS $$
  SELECT coalesce(
    current_setting('request.jwt.claims', true)::json -> 'app_metadata' ->> 'role',
    ''
  ) = 'super_admin';
$$ LANGUAGE sql STABLE;

-- RLS: only super_admin can read/write system_settings
ALTER TABLE system_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY admin_read ON system_settings FOR SELECT USING (is_super_admin());
CREATE POLICY admin_write ON system_settings FOR UPDATE USING (is_super_admin());

-- ============================================================
-- 2. User Preferences (per-user, theme + notifications)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_preferences (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  theme text NOT NULL DEFAULT 'system',
  notifications_enabled boolean NOT NULL DEFAULT true,
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
CREATE POLICY prefs_select ON user_preferences FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY prefs_insert ON user_preferences FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY prefs_update ON user_preferences FOR UPDATE USING (auth.uid() = user_id);
