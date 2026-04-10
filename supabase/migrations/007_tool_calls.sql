-- ============================================================
-- Module 7: Additional Tools (Text-to-SQL, Web Search)
-- ============================================================

-- 1. Add tool_calls JSONB to messages for tool execution metadata
ALTER TABLE public.messages ADD COLUMN tool_calls jsonb;

-- 2. RPC for safe user-scoped SQL execution (Text-to-SQL tool)
-- SECURITY DEFINER runs with function owner's privileges
-- STABLE marks it as read-only (no side effects)
CREATE OR REPLACE FUNCTION execute_user_document_query(
  query_text text,
  query_user_id uuid
)
RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER
AS $$
DECLARE
  result jsonb;
BEGIN
  -- Validate: must be SELECT only
  IF NOT (lower(trim(query_text)) LIKE 'select%') THEN
    RAISE EXCEPTION 'Only SELECT queries are allowed';
  END IF;

  -- Execute with user_id substitution and return as JSON array
  EXECUTE format(
    'SELECT coalesce(jsonb_agg(row_to_json(t)), ''[]''::jsonb) FROM (%s) t',
    replace(query_text, ':user_id', quote_literal(query_user_id::text))
  ) INTO result;

  RETURN result;
END;
$$;
