-- Migration 033: Web Search Toggle (ADR-0008)
-- Adds system-level kill switch and per-user default for web search.
-- Per-message override is a request-time field, not stored.

ALTER TABLE system_settings
    ADD COLUMN IF NOT EXISTS web_search_enabled BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS web_search_default BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN system_settings.web_search_enabled IS 'ADR-0008 L1: admin kill switch for web search. When false, web_search tool is never registered.';
COMMENT ON COLUMN user_preferences.web_search_default IS 'ADR-0008 L2: per-user default. Per-message override (L3) takes precedence when provided.';
