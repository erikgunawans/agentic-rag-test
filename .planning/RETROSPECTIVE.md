# Retrospective: LexCore

## Milestone: v1.0 — PII Redaction System

**Shipped:** 2026-04-29
**Phases:** 6 | **Plans:** 44 | **Duration:** 4 days (Apr 25–29)

### What Was Built

1. Presidio + spaCy NER with two-pass thresholds, UUID filter, 16 entity types, Indonesian gender-matched Faker surrogates (Phase 1)
2. Conversation-scoped entity registry — Supabase-persisted, asyncio-locked, race-protected (Phase 2)
3. Three-mode entity resolution + pre-flight egress filter + admin settings UI for all provider/mode config (Phase 3)
4. Placeholder-tokenized 3-phase de-anonymization, Jaro-Winkler fuzzy matching, LLM missed-PII scan, system-prompt guidance (Phase 4)
5. End-to-end chat-loop integration: buffering, SSE status events, symmetric tool/sub-agent coverage, D-48 egress fix, DB-backed toggle (Phase 5)
6. EMBEDDING_PROVIDER switch, graceful LLM-failure degradation, thread_id correlation logging, latency gate (Phase 6)

### What Worked

- **Parallel worktree agent execution** was highly effective — Phases 5 and 6 used 2-4 concurrent worktrees, cutting wall-clock time significantly. Wave discipline (blocking plans before parallel plans) prevented merge conflicts.
- **TDD with RED → GREEN discipline** in Phase 3 and 6 gave clean confidence gates. Plans that started with failing tests then wired real implementations caught real bugs earlier (e.g., `_StubRegistry` missing `thread_id` caught in Phase 6 Wave 2 immediately on first run).
- **CONTEXT.md discussion phase** surfaced critical architectural decisions early (D-31 async-lock, D-48 canonical-only egress, D-84 early-return gate) before any code was written. Decisions with clear rationale in CONTEXT.md were rarely revisited.
- **Phase SUMMARY.md one-liners** made `/gsd-progress` fast and informative throughout — good habit to write them carefully.
- **Brownfield bootstrap pattern** (GSD `--brownfield` with a Validated Baseline section) worked cleanly for a mature codebase. No friction from legacy requirements.

### What Was Inefficient

- **REQUIREMENTS.md traceability table not updated incrementally** — stayed stale throughout execution (observed as far back as Apr 27 after Phase 4). At milestone close, it showed all v1.0 requirements as `☐ Pending` despite 6 phases being complete. Future milestones should update the traceability table as each phase closes, or at minimum as each verification passes.
- **VERIFICATION.md anti-patterns were stale at write time** — both chat.py gaps had been fixed by commit `827690c` before the Phase 6 verifier ran, but the verifier agent read a stale worktree snapshot. Root cause: verifier ran against Phase 6 worktree state, not master. The fix: verifier should always check `git log --oneline -3` to detect whether the artifact it flagged was already fixed before writing a gap.
- **Phase 5 gap-closure (05-07, 05-08, 05-09) not in original roadmap** — three additional plans were needed after Phase 5 "complete" because D-48 (false-positive egress trips) and the DB-backed toggle were missed in planning. The discussion phase for Phase 5 should have surfaced the D-48 egress edge case. In retrospect, the egress filter needed an end-to-end production test case during Phase 3 planning, not just unit tests.
- **Disk-full on /private/tmp blocking early Phase 1 planning** — caused one full restart of the planning checker round. Unrelated to project work but wasted a cycle.
- **`gsd-sdk query milestone.complete` version parsing bug** — SDK returned `"version required for phases archive"` error during milestone close, requiring full manual archival. Filed as SDK issue.

### Patterns Established

- **Canonical-only egress scan** (D-48): only the longest real value per surrogate used in egress, not all variants. Prevents false-positive trips on legal vocabulary. Any future features involving PII egress checking should use `registry.canonicals()`.
- **`thread_id` correlation logging**: every async redaction operation logs `thread_id=%s` in debug/warning/info. All new services in the redaction subsystem should follow this pattern.
- **Lazy-singleton for NER models**: Presidio AnalyzerEngine, gender-detection model, and nickname dictionary loaded once at startup. Pattern should be followed for any future ML model additions.
- **`@pytest.mark.slow` for hardware-dependent tests**: PERF-02 style — real Presidio, `pytest.skip()` at primary threshold on slow hardware, hard assert at secondary threshold. Good pattern for latency regression gates.
- **Two-SUMMARY approach for gap-closure plans**: Plans 05-07, 05-08, 05-09 were gap-closure plans appended to a "complete" phase. Writing them as separate plans with their own SUMMARY.md (not appended to prior plans) kept the artifact trail clean.

### Key Lessons

1. **Update the traceability table at every phase verification pass**, not at milestone close. The table being stale for 4 days created unnecessary noise.
2. **CONTEXT.md discussion is worth the investment** — every plan that skipped discussion (e.g., Phase 6 06-02 pytest marker) took minutes; plans that skipped discussion AND had architectural ambiguity (D-48, title-gen fallback) needed gap-closure work.
3. **Verifier agents should check git log before flagging anti-patterns** — if a fix was committed in the same milestone execution, a `git log --oneline -5 [file]` call would catch it.
4. **Production smoke tests should cover the egress path** — the D-48 bug was found via a production thread (bf1b7325), not via the test suite. A test asserting `no false-positive egress trips on legal vocabulary samples` would have caught it earlier.
5. **4-day velocity for 44 plans is sustainable** — but only because planning artifacts (CONTEXT.md) were thorough. Plans that had vague "See Phase X discussion" references instead of explicit decision logs required re-reading prior context.

### Cost Observations

- Model mix: ~70% sonnet (executor), ~30% opus (planner/verifier)
- Parallel worktree agents: 2–4 concurrent (Phases 5–6)
- Notable: Phase 2 pytest coverage plan (02-06) against live Supabase DB was most expensive single plan — real async DB calls against `entity_registry`

---

## Cross-Milestone Trends

| Metric | v1.0 |
|--------|------|
| Phases | 6 |
| Plans | 44 |
| Duration | 4 days |
| Tests at close | 352 |
| Migrations | 5 (029–033) |
| Gap-closure plans | 3 (05-07, 05-08, 05-09) |
| Verification status | 5/6 passed, 1 human_needed (PERF-02) |
| Open deferred items | 1 (PERF-02 hardware run) |

---

*Created: 2026-04-29 after v1.0 milestone close*
