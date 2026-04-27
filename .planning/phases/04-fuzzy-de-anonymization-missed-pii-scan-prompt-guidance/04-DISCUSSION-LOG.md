# Phase 4: Fuzzy De-anonymization, Missed-PII Scan & Prompt Guidance - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-27
**Phase:** 04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance
**Areas discussed:** Fuzzy algorithm & library, 3-phase pipeline integration, Missed-PII scan placement, System-prompt guidance placement

---

## Area 1 — Fuzzy Algorithm & Library

### Q1: Which library/algorithm for the Jaro-Winkler ≥ 0.85 fuzzy match?

| Option | Description | Selected |
|--------|-------------|----------|
| `rapidfuzz` (Recommended) | C-extension Jaro-Winkler. Already a transitive dependency of Presidio — zero new top-level dep. Battle-tested; matches PRD FR-5.4 algorithm choice exactly. | ✓ |
| `python-Levenshtein` | Different algorithm (edit distance, not Jaro-Winkler); less linguistically appropriate for proper-name fuzziness. Would require porting the threshold semantics. | |
| `jellyfish` | Pure-Python Jaro-Winkler. Cleaner API but ~50× slower than rapidfuzz at warm-path scale. | |
| Custom implementation | Reinvent the algorithm in pure Python. Avoids any dep but throws away decades of edge-case fixing. | |

**User's choice:** `rapidfuzz`
**Notes:** Captured as D-67. Rationale: zero new dep + C-extension speed + PRD-aligned algorithm.

---

### Q2: How is the fuzzy candidate set scoped?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-cluster variants only (Recommended) | Score `mangled_text` against the cluster's variant rows from Phase 3 D-48 (canonical + first-only + last-only + honorific-prefixed + nickname). Highest score wins if it clears the threshold. | ✓ |
| Cross-cluster scoring | Score against ALL surrogates in the registry. Catches mangled mentions even when cluster-association is unclear, but introduces corruption risk: two distinct people whose surrogates happen to be similar could merge. | |
| Full-thread token-bag | Build a bag-of-tokens from every registered variant; score `mangled_text` tokens against the bag. Scales poorly; produces ambiguous matches. | |
| Only-canonical scoring | Score only against each cluster's canonical surrogate. Simpler but defeats Phase 3 D-48's whole purpose (sub-surrogate variants). | |

**User's choice:** Per-cluster variants only
**Notes:** Captured as D-68. Rationale: leverages Phase 3 D-48's variant rows; avoids cross-cluster corruption.

---

### Q3: How is the threshold configured?

| Option | Description | Selected |
|--------|-------------|----------|
| Single env var, default 0.85 + DB column (Recommended) | `FUZZY_DEANON_THRESHOLD` env + `system_settings.fuzzy_deanon_threshold` column. Defense-in-depth: Pydantic range validator at API + DB CHECK at data layer. Reads via existing `get_system_settings()` 60s TTL cache. | ✓ |
| Per-mode thresholds | Separate threshold for algorithmic vs LLM modes. Doubles config surface; no PRD evidence two thresholds are needed. | |
| Hard-coded constant | Fix at 0.85 in code. Loses runtime tunability that ops will want. | |

**User's choice:** Single env var, default 0.85
**Notes:** Captured as D-69. Same defense-in-depth pattern as Phase 3 D-57.

---

### Q4: What pre-fuzzy normalization runs before Jaro-Winkler scoring?

| Option | Description | Selected |
|--------|-------------|----------|
| Strip honorifics + casefold + token-level scoring (Recommended) | Three-step normalization: (1) strip honorifics from `honorifics.py`, (2) `.casefold()` both strings, (3) split into whitespace tokens and score each token against each variant token, take max. Composes with Phase 2 D-36's casefold invariant. | ✓ |
| Casefold only | Just lowercase before scoring. Misses "pak Smith" vs registry's "Pak Smith" alignment. | |
| Word-bag/Jaccard pre-step | Tokenize and score on token overlap before Jaro-Winkler. Redundant — Jaro-Winkler already handles partial matches. | |
| Full-string scoring without tokenization | Don't tokenize; score the full string against each variant. Misses "John A. Smith" vs "John Smith" cases. | |

**User's choice:** Strip honorifics + casefold + token-level scoring
**Notes:** Captured as D-70. Reuses Phase 1 honorifics constants; preserves Phase 2 D-36 invariant.

---

## Area 2 — 3-Phase Pipeline Integration

### Q5: How does the `de_anonymize_text` method evolve?

| Option | Description | Selected |
|--------|-------------|----------|
| Upgrade in-place, new param (Recommended) | Extend Phase 2's `de_anonymize_text(text, registry, mode: Literal['algorithmic','llm','none'] | None = None)`. When `mode is None`, resolve via env → DB → default `none`. Default `none` keeps Phase 2 tests green. | ✓ |
| New method `de_anonymize_text_v2` | Add a separate v2 method; Phase 5 hand-migrates each callsite. Forces churn for no benefit. | |
| Service-level dispatcher | Add a `RedactionDispatcher` class that picks v1 or v2 method. Adds a layer with no functional value. | |

**User's choice:** Upgrade in-place, new param
**Notes:** Captured as D-71. Phase 2 D-34 docstring explicitly promised this.

---

### Q6: Where does mode dispatch happen, and how does fuzzy LLM mode invoke the provider?

| Option | Description | Selected |
|--------|-------------|----------|
| Resolve in service, call via LLMProviderClient (Recommended) | RedactionService reads effective mode (param → env → DB → default). For `llm`: invoke `await llm_provider.call(feature='fuzzy_deanon', messages=..., registry=registry)`. Egress filter from Phase 3 D-53..D-56 still runs. | ✓ |
| Routing in LLMProviderClient | Push the algorithmic vs LLM branch into the provider client. Mixes resolution policy with transport. Loses the algorithmic path entirely from the client's surface. | |
| Separate `FuzzyResolver` class | New class wraps both modes + dispatch. Premature abstraction for one conditional in one method. | |

**User's choice:** Resolve in service, call via LLMProviderClient
**Notes:** Captured as D-72. Reuses Phase 3 D-49 client; egress filter is defense-in-depth.

---

### Q7: What does the LLM see in fuzzy LLM mode?

| Option | Description | Selected |
|--------|-------------|----------|
| Placeholder-tokenized text in, JSON list out (Recommended) | LLM input: text where every known surrogate is already `<<PH_xxxx>>` (Pass 1 done) + JSON variant list `[{token, canonical, variants}, ...]`. LLM output: Pydantic-validated `{matches: [{span, token}, ...]}`. Cloud LLM sees zero raw real values. | ✓ |
| Send raw text to LLM | Defeats placeholder-tokenization invariant — privacy regression. Not acceptable. | |
| Boolean classifier per cluster | LLM only flags "does this cluster have a mangled mention?" Loses per-mention granularity — multiple mangled surrogates in same cluster need distinct matches. | |

**User's choice:** Placeholder-tokenized text in, JSON list out
**Notes:** Captured as D-73. Server resolves spans to positions via `re.escape`.

---

### Q8: How does hard-redact survival work?

| Option | Description | Selected |
|--------|-------------|----------|
| Inherit from Phase 2 design (Recommended) | Hard-redact placeholders are NEVER in the registry per Phase 2 D-24 / REG-05. Pass 1 can't replace them; Pass 2 fuzzy operates on cluster variants only — also can't match `[CREDIT_CARD]`; Pass 3 knows about `<<PH_xxxx>>` only. Add explicit assertion test across all 3 modes. | ✓ |
| Explicit hard-redact filtering pass | Add a runtime filter that excludes `[A-Z_]+` patterns from fuzzy candidates. Redundant — invariant is already structural. | |
| Runtime regex check for `\[[A-Z_]+\]` patterns | Defensive guard. False positives on legal-doc citations like "[CONTRACT]". | |

**User's choice:** Inherit from Phase 2 design
**Notes:** Captured as D-74. Add explicit assertion test (cheap insurance).

---

## Area 3 — Missed-PII Scan Placement

### Q9: Where in the redaction-service pipeline does the missed-PII scan slot in?

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-chain inside redact_text (Recommended) | `redact_text()` runs: detect → anonymize → missed-scan → re-NER-if-replaced → return. Gated by `PII_MISSED_SCAN_ENABLED`. Existing/Phase-5 callers get the scan for free, no extra wiring. | ✓ |
| Separate `scan_for_missed_pii` method, caller decides | `redact_text()` unchanged; expose `RedactionService.scan_for_missed_pii(anonymized_text)` — Phase 5 chat-loop invokes it explicitly. Adds wiring concern; risk of forgotten calls in sub-agent paths. | |
| Auto-chain on input only, expose method for output-side | Auto-chain on user-input/tool-result anonymization, expose method for output-side use after de-anon. Optimizes for primary use case but Phase 5 still has work. | |

**User's choice:** Auto-chain inside redact_text
**Notes:** Captured as D-75. FR-8.1 says scan operates on already-anonymized text — input is privacy-safe by construction.

---

### Q10: When the scan replaces text, what scope does the primary NER re-run cover (FR-8.5)?

| Option | Description | Selected |
|--------|-------------|----------|
| Full re-run of redact_text on modified text (Recommended) | Treat post-replacement text as fresh input — re-detect all entities, re-anchor existing surrogates by registry lookup, re-emit anonymized output. Simplest, most correct, position-safe. Bounded: single re-run cap; second-pass entities log at WARNING and skip another re-run. | ✓ |
| Re-position existing surrogates only (no NER re-run) | Walk modified text, re-find each registry surrogate by string search, recompute positions. Faster but assumes no new entities surface in remaining text. | |
| Localized NER re-run around replaced spans only | Re-run NER on a window (±200 chars) around each replaced span, splice positions back. Most efficient but complex bookkeeping; missed-scan replacements are rare so perf gain is marginal. | |

**User's choice:** Full re-run of redact_text on modified text
**Notes:** Captured as D-76. PRD FR-8.5 explicitly mandates re-run.

---

### Q11: What's the LLM response schema for the missed-PII scan?

| Option | Description | Selected |
|--------|-------------|----------|
| List of {type, text} pairs, server substring-matches (Recommended) | LLM returns `[{type: 'CREDIT_CARD', text: '4111 1111 1111 1111'}, ...]`. Server uses `re.escape(text)` to locate ALL occurrences in anonymized text. LLMs unreliable at character offsets — let server do positions. | ✓ |
| List of {type, text, start, end} with positions | LLM returns full positional info. Strict — but if positions drift even one char, replacement corrupts surrounding text. | |
| Boolean per entity type ("missed any credit cards? yes/no") | Coarse classifier — server then runs targeted regex/scan for that type. Decouples LLM from text extraction but adds a regex step per flagged type. | |

**User's choice:** List of {type, text} pairs, server substring-matches
**Notes:** Captured as D-77. Same lesson as Phase 1 B2: position arithmetic is brittle.

---

### Q12: How does observability handle the (PERF-04-mandated) soft-fail when scan provider is unavailable?

| Option | Description | Selected |
|--------|-------------|----------|
| Warn-log + traced span tag + counter metric (Recommended) | On timeout/5xx/network: log WARNING with `feature='missed_scan'`, provider, error_class (no PII), tag the `@traced` span with `scan_skipped=true` and reason, increment a counter. Anonymization continues with primary NER results only. | ✓ |
| Warn-log only (no metrics, no span tags) | Minimal observability — just a warning log. Simplest, but ops can't see scan health over time without grepping logs. | |
| Hard-fail in cloud mode, soft-fail in local mode | Privacy-strict reading: if cloud scan fails the request fails (since scan is enabled, the user expects it). Local scan stays best-effort. Contradicts PERF-04 explicitly — would need a requirements amendment. | |

**User's choice:** Warn-log + traced span tag + counter metric
**Notes:** Captured as D-78. PERF-04 explicitly says "skipped, never crash, never leak".

---

## Area 4 — System-Prompt Guidance Placement

### Q13: Where does the surrogate-preservation guidance get injected?

| Option | Description | Selected |
|--------|-------------|----------|
| Centralized helper, appended in both chat.py + agent_service.py (Recommended) | Define `PII_PRESERVATION_GUIDANCE` in `app/services/redaction/prompt_guidance.py`. Chat router's SYSTEM_PROMPT and each of the 4 agent system_prompts call `get_pii_guidance_block()` and append. One source of truth, no duplication, covers main-agent + sub-agents (TOOL-01..04 carry-forward). | ✓ |
| Only chat.py SYSTEM_PROMPT | Simplest — only main agent gets the guidance. Sub-agents (Research Agent, etc.) won't preserve surrogates reliably. Acceptable if Phase 5 punts on sub-agent coverage. | |
| Only agent_service.py per-agent prompts | Each of the 4 agent definitions gets the guidance directly inlined. No helper. Covers sub-agents but chat.py main-agent path needs duplicate copy. Fragile when prompts evolve. | |

**User's choice:** Centralized helper, appended in both
**Notes:** Captured as D-79. Same "small focused module per concern" pattern as Phase 1.

---

### Q14: When does the guidance block get appended to the system prompt?

| Option | Description | Selected |
|--------|-------------|----------|
| Only when redaction is enabled for the thread (Recommended) | Append the block conditionally based on the thread's redaction flag. When redaction is off, no surrogates exist — the guidance is dead weight that confuses the LLM. Thread-level check is cheap. | ✓ |
| Always inject (every request) | Append unconditionally. Simpler — no flag check at prompt-build time. Costs ~150 tokens per request even when redaction is disabled. | |
| Conditional on registry having >0 surrogates for the thread | Most surgical — only inject when there's actually something to preserve. Requires a per-message registry-count check. Saves tokens on early turns of a redaction-on thread before any PII appears. | |

**User's choice:** Only when redaction is enabled for the thread
**Notes:** Captured as D-80. Thread-level flag is cheap; registry-count check is overkill.

---

### Q15: What language should the guidance block be written in?

| Option | Description | Selected |
|--------|-------------|----------|
| English-only (Recommended) | System-prompt instruction blocks are most reliable in English across all LLM providers (OpenRouter, OpenAI, local LM Studio/Ollama). Indonesian user content + English instructions is the standard LexCore pattern — LLM follows instruction language regardless of content language. | ✓ |
| Indonesian-first with English fallback | Aligns with LexCore i18n default (Indonesian). Risks weaker instruction-following on smaller local models that are English-dominant. Bilingual prompt would be ~2x longer. | |
| Bilingual (Indonesian + English in same block) | Maximum coverage — instruction appears in both languages. Strongest instruction-following, but adds ~150 tokens per turn. | |

**User's choice:** English-only
**Notes:** Captured as D-81. Existing LexCore tool-calling logic already follows this convention.

---

### Q16: What does the guidance block actually say (content density)?

| Option | Description | Selected |
|--------|-------------|----------|
| Imperative rules + explicit type list + [TYPE] warning + 1-2 examples (Recommended) | Strict 'MUST reproduce... NEVER abbreviate' phrasing, lists the surrogate types (names, emails, phones, locations, dates, URLs, IPs), explicitly warns about [TYPE] placeholders being literal, and includes a concrete example. Examples make LLMs comply much more reliably than abstract rules. | ✓ |
| Imperative rules + type list, no examples | Strict phrasing, lists types covered, but no concrete examples. Shorter (~80 tokens vs ~150). Examples are the highest-leverage part of instruction-following — dropping them risks weaker compliance. | |
| Soft prose ('please preserve names, emails, etc.') | Polite, non-imperative phrasing. Token-efficient but historically weaker compliance — LLMs trained on RLHF interpret 'please' as optional. | |

**User's choice:** Imperative rules + type list + [TYPE] warning + examples
**Notes:** Captured as D-82. Examples are load-bearing — RLHF interprets "please" as optional.

---

## Closing Check

**Question:** Any more Phase 4 gray areas to discuss, or write CONTEXT.md now?

| Option | Description | Selected |
|--------|-------------|----------|
| Write CONTEXT.md + DISCUSSION-LOG.md now (Recommended) | 16 decisions captured (D-67..D-82) cover the load-bearing architecture. Remaining decisions (migration 031 columns, perf budgets, test matrix) are planning-level — the planner handles them. | ✓ |
| One more area: performance budgets | Discuss latency targets for fuzzy de-anon and missed-scan. PRD PERF-02 says <500ms for redaction; Phase 4 may push past. | |
| One more area: migration 031 schema | Decide column names/types for fuzzy_deanon_mode and fuzzy_deanon_threshold. | |
| One more area: test matrix coverage | Decide whether SC#1..SC#5 each need a dedicated test file, or one consolidated test_phase4.py. | |

**User's choice:** Write CONTEXT.md + DISCUSSION-LOG.md now
**Notes:** Captured 16 decisions D-67..D-82 in `.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md`.

---

## Decision Index

| ID | Topic | Captured Where |
|----|-------|----------------|
| D-67 | rapidfuzz library for Jaro-Winkler | CONTEXT.md `<decisions>` |
| D-68 | Per-cluster variant scoping | CONTEXT.md `<decisions>` |
| D-69 | Single env var + DB column threshold (default 0.85) | CONTEXT.md `<decisions>` |
| D-70 | Pre-fuzzy normalization (strip honorifics + casefold + token-level) | CONTEXT.md `<decisions>` |
| D-71 | In-place upgrade of de_anonymize_text with mode parameter | CONTEXT.md `<decisions>` |
| D-72 | Service-resolved mode dispatch via LLMProviderClient | CONTEXT.md `<decisions>` |
| D-73 | Placeholder-tokenized text in, JSON `[{span, token}]` out | CONTEXT.md `<decisions>` |
| D-74 | Hard-redact survival inherited from Phase 2 D-24 / REG-05 | CONTEXT.md `<decisions>` |
| D-75 | Auto-chain missed-scan inside redact_text | CONTEXT.md `<decisions>` |
| D-76 | Full re-run of redact_text on modified text (single re-run cap) | CONTEXT.md `<decisions>` |
| D-77 | LLM response: `[{type, text}]` + server `re.escape` substring-match | CONTEXT.md `<decisions>` |
| D-78 | Soft-fail: warn-log + span tag + counter metric | CONTEXT.md `<decisions>` |
| D-79 | Centralized helper appended in both chat.py + agent_service.py | CONTEXT.md `<decisions>` |
| D-80 | Conditional injection — only when redaction enabled for thread | CONTEXT.md `<decisions>` |
| D-81 | English-only phrasing | CONTEXT.md `<decisions>` |
| D-82 | Imperative rules + type list + [TYPE] warning + examples | CONTEXT.md `<decisions>` |
