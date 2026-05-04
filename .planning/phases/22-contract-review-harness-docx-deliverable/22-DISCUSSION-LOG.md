# Phase 22: Contract Review Harness + DOCX Deliverable - Discussion Log

**Discussed:** 2026-05-04
**For human reference only — not consumed by downstream agents.**

This log captures the full Q&A trail. CONTEXT.md captures the locked decisions.

---

## Pre-discussion Setup

**Phase scope from REQUIREMENTS.md and ROADMAP.md (already locked):**
- 8 CR-* requirements (Document Intake → Classify → Gather Context → Load Playbook → Clause Extraction → Risk Analysis → Redlines → Executive Summary)
- 8 DOCX-* requirements (title page → exec summary → key findings → redline table → acceptable clauses → next steps → non-fatal fallback)
- 13 clause categories specified
- GREEN/YELLOW/RED grading
- batch_size=5 for CR-06/07
- 50k-token threshold for clause-chunking in CR-05

**Carrying forward (not re-asked):**
- Phase 21 D-01..D-04 (HIL pattern) — applies to CR-03
- Phase 21 D-05..D-09 (batch JSONL + frontend slice) — applies to CR-06/07
- Phase 20 gatekeeper sentinel + B4 single-registry — applies to all LLM calls
- Phase 21 CR-21-08 (deferred LLM trigger reliability) — must address in Phase 22

**Areas presented and selected:** all 4 areas — Gatekeeper trigger, Playbook discovery, CR-03 HIL UX, DOCX template + delivery.

---

## Area 1: Gatekeeper Trigger Reliability (CR-21-08 fix)

### Q1.1 — Trigger approach
**Options:** Workspace-aware gatekeeper prompt (Recommended) / Stronger model / UI button / Hybrid
**User selected:** Workspace-aware gatekeeper prompt
**Rationale:** Keeps natural-language UX; structurally fixes the LLM's blindness to workspace state; ~30 line change in gatekeeper.py vs. wholesale model swap or new UI surface.

### Q1.2 — Workspace block format
**Options:** Filename + size only (Recommended) / Filename + first 200 chars / Filename + count only / Full metadata
**User selected:** Filename + size only
**Rationale:** Compact, sufficient for "is a contract uploaded" verification, no PII through content peek, no extra token cost.

### Q1.3 — Trigger phrase strategy
**Options:** Match intent not phrase (Recommended) / Require explicit harness name / Auto-trigger on upload / Two-step confirmation
**User selected:** Match intent, not phrase
**Rationale:** Most natural UX; covered by 3-5 few-shot examples in the system prompt.

### Q1.4 — Eval / regression strategy
**Options:** Eval set + automated test (Recommended) / Manual UAT only / Mocked unit tests only / Eval + LangSmith telemetry
**User selected:** Eval set + automated test
**Rationale:** Protects smoke-echo trigger reliability from regressing as we tune Contract Review prompts; CI-runnable; LangSmith dashboard deferred to keep Phase 22 small.

---

## Area 2: Playbook Discovery Scope (CR-04)

### Q2.1 — Playbook source
**Options:** Tag-based filter on `playbook` (Recommended) / Whole library / Curated /playbooks folder / Two-tier with fallback
**User selected:** Tag-based filter on `playbook`
**Rationale:** Clean separation, predictable, reuses existing `filter_tags` parameter on `search_documents`.

### Q2.2 — Playbook output shape
**Options:** Doc IDs + titles + per-category mappings (Recommended) / Full extracted clause language / Summary digest only / Hybrid markdown + JSON
**User selected:** Doc IDs + titles + per-clause-category mappings
**Rationale:** Per REQUIREMENTS.md spec; sub-agents call `search_documents` with `filter_doc_ids` per category for precise grounding.

### Q2.3 — Empty-playbook fallback
**Options:** Generic legal-knowledge fallback (Recommended) / Hard fail / Ask user mid-flow / Auto-expand to whole library
**User selected:** Generic legal-knowledge fallback with `unfounded` flag
**Rationale:** User still gets useful output without being blocked by an empty corpus; honest about limitations via summary callout.

### Q2.4 — Authority hierarchy
**Options:** User-uploaded > regulatory > 3rd-party (Recommended) / Recency-weighted / User-curated authority field / LLM judges per-clause
**User selected:** User-uploaded > regulatory > 3rd-party
**Rationale:** Matches typical legal team intuition ("our standards first, then law, then market"); no admin UI work needed.

---

## Area 3: CR-03 HIL Question UX

### Q3.1 — Pacing
**Options:** One combined question, free-form (Recommended) / Sequential 4 pauses / Structured form prompt / LLM picks 1-3 topics
**User selected:** One combined question, free-form answer
**Rationale:** Lowest friction; matches Phase 21 HIL design; respects users who want to skip-or-summarize.

### Q3.2 — Persistence shape
**Options:** Raw text downstream LLMs interpret (Recommended) / LLM-parsed JSON / Hybrid raw + JSON / Two-pass with confirmation
**User selected:** Raw text only, downstream LLMs interpret
**Rationale:** No parser to maintain, no extra LLM call; LLMs are good at extracting fields from natural language.

### Q3.3 — Skip handling
**Options:** Accept any reply, default to neutral (Recommended) / Re-prompt 1x if very short / Hard-require non-empty / Allow empty + downgrade quality flag
**User selected:** Accept any reply, default to neutral
**Rationale:** Don't fight users who want to skip; respect their time; sub-agents handle sparse context gracefully.

---

## Area 4: DOCX Template + Delivery

### Q4.1 — Generation approach
**Options:** Pure programmatic python-docx (Recommended) / .dotx template merge / Markdown + pandoc / HTML → docx
**User selected:** Pure programmatic python-docx
**Rationale:** Simplest, version-controlled, deterministic; matches REQUIREMENTS.md verbatim.

### Q4.2 — Risk color scheme
**Options:** Pastel red/yellow/green (Recommended) / PJAA brand purple + colored text / Bold + emoji prefix only / Saturated fills
**User selected:** Pastel red/yellow/green (#E6F4EA / #FEF7E0 / #FCE8E6)
**Rationale:** Industry-standard, professional, prints well, matches LexCore's calibrated-restraint design language.

### Q4.3 — Delivery mechanism
**Options:** Inline chat bubble + workspace panel (Recommended) / Workspace panel only / Inline link only / Auto-download
**User selected:** Inline chat bubble link + workspace panel listing, no auto-download
**Rationale:** User sees it both ways — chat link is immediate, panel is durable; no pop-up annoyances.

### Q4.4 — DOCX-08 fallback UX
**Options:** Markdown bubble + visible failure note (Recommended) / Silent fallback / Retry button / Hard fail entire harness
**User selected:** Markdown bubble + visible non-fatal failure note
**Rationale:** User still gets the analysis; ops visibility through LangSmith logging; doesn't clobber usable output (DOCX-08 is non-fatal by spec).

---

## Out-of-scope items deferred (with reasons)

- **Multi-contract batch review** — would require harness-level parallelism, separate phase.
- **DOCX styling beyond pastel + CONFIDENTIAL marker** — design exploration deferred to enhancement phase.
- **Admin authority_score field** — adds admin UI work outside Phase 22.
- **Two-pass user confirmation on CR-03 parsed fields** — adds HIL pause; deferred unless accuracy issues surface.
- **LangSmith production trigger-rate dashboard** — eval set covers CI; telemetry can come later.
- **Curated /playbooks folder option** — alternative to tag approach; can be added if tag discipline becomes a problem.
- **Retry button on failed DOCX export** — D-22-15's plain-text note suffices for v1.

---

## Claude's Discretion (decisions made without asking the user)

- **No new harness phase types** — the 5 existing types (programmatic / llm_single / llm_agent / llm_human_input / llm_batch_agents) cover all 8 CR phases. No engine extension needed.
- **No new migration** — `harness_runs` schema covers everything; the workspace_files table covers DOCX delivery.
- **Egress filter on every CR LLM call** — already enforced by the Phase 20 B4 single-registry pattern; not a Phase 22 decision.
- **Phase 22 success criteria from ROADMAP locked verbatim** — no scope changes during discussion.
