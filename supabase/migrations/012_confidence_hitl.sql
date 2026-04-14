-- ============================================================
-- Feature 2: AI Confidence Scoring & HITL Gates
-- ============================================================

-- 1. Add confidence and review columns to document_tool_results
alter table public.document_tool_results
  add column confidence_score double precision,
  add column review_status text not null default 'auto_approved',
  add column reviewed_by uuid references auth.users(id),
  add column reviewed_at timestamptz,
  add column review_notes text;

alter table public.document_tool_results
  add constraint chk_review_status
  check (review_status in ('auto_approved', 'pending_review', 'approved', 'rejected'));

-- 2. Add confidence threshold to system_settings
alter table public.system_settings
  add column confidence_threshold double precision not null default 0.85;

update public.system_settings set confidence_threshold = 0.85 where id = 1;

-- 3. Index for review queue queries
create index idx_dtr_review_status
  on public.document_tool_results(review_status)
  where review_status = 'pending_review';

-- 4. Allow admins to read ALL tool results (for review queue)
-- Drop existing select policy that restricts to own rows, replace with broader one
drop policy if exists "users see own tool results" on public.document_tool_results;
drop policy if exists "see own tool results" on public.document_tool_results;

create policy "users_and_admins_see_tool_results"
  on public.document_tool_results for select to authenticated
  using (
    auth.uid() = user_id
    or (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

-- 5. Allow admins to update review fields on any row
create policy "admins_update_review"
  on public.document_tool_results for update to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin')
  with check ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');
