-- Migration 034: skills table + RLS + seed skill-creator
-- Phase 7 / Plan 07-01 — closes SKILL-10
-- All operations are idempotent (CREATE IF NOT EXISTS / ON CONFLICT DO NOTHING)

-- ============================================================
-- 1. TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS public.skills (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID REFERENCES auth.users(id) ON DELETE CASCADE,  -- NULL = global skill
  created_by    UUID REFERENCES auth.users(id) ON DELETE SET NULL, -- NULL = system seed
  name          TEXT NOT NULL,
  description   TEXT NOT NULL,
  instructions  TEXT NOT NULL,
  enabled       BOOLEAN NOT NULL DEFAULT true,
  metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,   -- license, compatibility, freeform tags
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 2. INDEXES
-- ============================================================

-- Unique name per user (case-insensitive) for private skills
CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_user_name
  ON public.skills (user_id, lower(name))
  WHERE user_id IS NOT NULL;

-- Unique name among global skills (case-insensitive)
CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_global_name
  ON public.skills (lower(name))
  WHERE user_id IS NULL;

-- For provenance lookups (who created a skill)
CREATE INDEX IF NOT EXISTS idx_skills_created_by
  ON public.skills (created_by);

-- ============================================================
-- 3. AUTO-UPDATE TRIGGER (reuses handle_updated_at from migration 001)
-- ============================================================

CREATE TRIGGER skills_handle_updated_at
  BEFORE UPDATE ON public.skills
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ============================================================
-- 4. ROW-LEVEL SECURITY (D-P7-05)
-- ============================================================

ALTER TABLE public.skills ENABLE ROW LEVEL SECURITY;

-- SELECT: user sees their own private skills OR any global skill (user_id IS NULL)
CREATE POLICY "skills_select"
  ON public.skills
  FOR SELECT
  USING (
    user_id = auth.uid()
    OR user_id IS NULL
  );

-- INSERT: caller may only create skills owned by themselves (no inserting globals via API)
CREATE POLICY "skills_insert"
  ON public.skills
  FOR INSERT
  WITH CHECK (
    created_by = auth.uid()
    AND user_id = auth.uid()
  );

-- UPDATE: user may only update their own private skills (global rows are service-role only)
CREATE POLICY "skills_update"
  ON public.skills
  FOR UPDATE
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- DELETE: only the original private owner may delete a skill they created; OR super_admin.
-- A creator cannot DELETE a globally-shared skill directly — they must first un-share it
-- (PATCH /skills/{id}/share {global: false}) to bring it back into their private namespace.
-- super_admin may delete any skill including globals (admin moderation, D-P7-04).
CREATE POLICY "skills_delete"
  ON public.skills
  FOR DELETE
  USING (
    (user_id = auth.uid() AND created_by = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

-- ============================================================
-- 5. SYSTEM SEED — skill-creator (D-P7-10, D-P7-11, SKILL-10)
-- ============================================================
-- Deterministic UUID: 00000000-0000-0000-0000-000000000007 (phase 7 sentinel)
-- user_id IS NULL  → global skill visible to all users
-- created_by IS NULL → system seed, not attributed to any user
-- ON CONFLICT DO NOTHING → idempotent re-apply

INSERT INTO public.skills (
  id,
  user_id,
  created_by,
  name,
  description,
  instructions,
  enabled
)
VALUES (
  '00000000-0000-0000-0000-000000000007',
  NULL,
  NULL,
  'skill-creator',
  'Helps users author new agent skills following the v1.1 SKILL.md format.',
  $skill_creator_body$
# skill-creator — Authoring Guide

You are a skill-authoring assistant for LexCore v1.1. Your purpose is to guide the user through creating a well-structured, reusable agent skill in the SKILL.md format and then saving it to the LexCore skills library.

## Skill Name Rules

- Use lowercase kebab-case only (a-z, 0-9, hyphens).
- Maximum 64 characters.
- The name must be unique within the user's private library. If a name conflicts with an existing skill, suggest a qualified variant (e.g., `reviewing-nda-clauses-strict`).
- Good examples: `reviewing-nda-clauses`, `summarizing-board-decisions`, `extracting-payment-terms`.

## Description Guidance

The description should answer two questions in two sentences or fewer:

1. **What does this skill do?** (concrete output: "Extracts all payment obligation clauses from a contract…")
2. **When is it triggered?** ("…when the user asks about payment terms, due dates, or financial obligations.")

Avoid vague descriptions like "helps with legal tasks." Be specific about the domain and trigger condition.

## Instructions Content

The instructions are the full prompt body that will be prepended to the system prompt when this skill is active. Write them as you would write a system prompt:

- Use Markdown headings and bullet lists for structure.
- State the skill's objective in the first paragraph.
- List the input format the skill expects and the output format it produces.
- Include any domain-specific rules, constraints, or terminology relevant to Indonesian law (UU PDP, BJR, OJK regulations, etc.) if applicable.
- Keep the total length under 500 lines. Concise skills outperform verbose ones.
- Do not include meta-instructions about how to use the skill itself — focus entirely on the task the skill performs.

## Legal-Domain Examples

### Example 1 — reviewing-nda-clauses

**Name:** `reviewing-nda-clauses`
**Description:** Reviews non-disclosure agreement clauses for completeness and enforceability under Indonesian law. Triggered when the user asks to review, analyze, or improve NDA terms.
**Instructions excerpt:** "You are an Indonesian legal reviewer specializing in confidentiality agreements. When given an NDA clause, identify: (1) missing essential elements (parties, duration, scope, penalties), (2) provisions that may be unenforceable under Indonesian contract law (KUHPerdata), and (3) recommended rewordings. Output a structured review with one section per clause."

### Example 2 — summarizing-board-decisions

**Name:** `summarizing-board-decisions`
**Description:** Produces a structured BJR-compliant summary of board meeting minutes. Triggered when the user uploads or pastes board minutes and asks for a summary or decision log.
**Instructions excerpt:** "You are a corporate governance analyst. Summarize board meeting minutes into: (1) decisions made with vote counts, (2) action items with responsible parties and deadlines, (3) risk flags requiring follow-up. Format as a numbered decision log compatible with the LexCore BJR module."

### Example 3 — extracting-payment-terms

**Name:** `extracting-payment-terms`
**Description:** Extracts and tabulates all payment obligations from a contract document. Triggered when the user asks about payment schedules, amounts, deadlines, or financial terms.
**Instructions excerpt:** "You are a contract analyst. Extract every payment obligation from the provided contract and output a table with columns: Clause Reference, Obligor, Amount (IDR or currency stated), Due Date / Trigger, Penalty for Late Payment. If any field is missing from the clause, mark it as 'Not specified'. Sort rows by due date ascending."

## Saving the Skill

Once you have helped the user finalize the skill name, description, and instructions, call the `save_skill` tool with the completed fields. Confirm the save succeeded and display the skill name and ID so the user can reference it later.

Do not ask the user to manually copy or paste the skill — always invoke `save_skill` directly.
$skill_creator_body$,
  true
)
ON CONFLICT (id) DO NOTHING;
