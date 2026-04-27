# Phase 4: Fuzzy De-anonymization, Missed-PII Scan & Prompt Guidance - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship the production-grade de-anonymization pipeline (placeholder-tokenized 3-phase) with optional fuzzy matching and LLM-driven missed-PII passes, plus the system-prompt guidance that keeps surrogates verbatim through model output. This is the privacy-correctness layer between Phase 3 (resolution + provider abstraction) and Phase 5 (chat-loop integration).

In scope:
- Fuzzy de-anonymization mode toggle (`FUZZY_DEANON_MODE` ∈ `algorithmic` | `llm` | `none`) with Jaro-Winkler ≥ 0.85 default threshold (`FUZZY_DEANON_THRESHOLD`).
- In-place upgrade of Phase 2's `RedactionService.de_anonymize_text` to a 3-phase placeholder-tokenized pipeline:
  1. **Pass 1:** Replace known surrogates → opaque `<<PH_xxxx>>` placeholders.
  2. **Pass 2 (NEW):** Fuzzy/LLM-match remaining text against the registry's variants, replacing matched mangled surrogates → placeholders. Bypassed when mode is `none`.
  3. **Pass 3:** Resolve all placeholders → real values.
- Algorithmic fuzzy matcher backed by `rapidfuzz` (already a transitive Presidio dep; zero new top-level dep). Pre-normalization: strip honorifics + casefold + token-level scoring.
- LLM fuzzy mode: cloud/local provider call via existing `LLMProviderClient.call(feature='fuzzy_deanon', ...)` (D-49). Cloud mode sees ONLY placeholder-tokenized text + JSON variant list — never raw real values.
- Optional secondary missed-PII LLM scan (`PII_MISSED_SCAN_ENABLED`, default `true`), auto-chained inside `RedactionService.redact_text`. Pipeline: detect → anonymize → missed-scan → re-anonymize-if-replaced → return.
- Missed-scan response schema: `[{type, text}]` pairs; server uses `re.escape(text)` substring matching to locate occurrences. Hard-redact entity-type validation (FR-8.4); invalid types discarded.
- Soft-fail observability for the scan: warn-log + `@traced` span tag (`scan_skipped=true`, reason, no PII) + counter metric. Anonymization continues with primary NER results when the scan provider is unavailable (PERF-04).
- System-prompt guidance helper module (`backend/app/services/redaction/prompt_guidance.py`) emitting the surrogate-preservation block. Appended to `chat.py` SYSTEM_PROMPT and to all 4 agents in `agent_service.py` via the same helper. Conditional on per-thread redaction-enabled flag.
- New migration `031_pii_fuzzy_settings.sql` adding `fuzzy_deanon_mode` + `fuzzy_deanon_threshold` columns to `system_settings` (composes with Phase 3's migration 030 and existing 60s TTL cache).
- Admin UI extension on the existing "PII Redaction & Provider" section: fuzzy mode dropdown + threshold slider.
- Pytest coverage for ROADMAP SC#1..SC#5 (mangled-surrogate resolution, surname-collision avoidance, hard-redact survival, missed-scan validation, prompt-driven verbatim emission).

Explicitly NOT in scope (deferred to later phases):
- Chat-loop integration: SSE buffering, `redaction_status` events, full tool/sub-agent symmetric coverage (Phase 5: BUFFER-01..03, TOOL-01..04). The Phase 4 prompt-guidance helper is created and wired, but the *invocation path* through chat completions remains Phase 5's job.
- Embedding-provider switch and `EMBEDDING_PROVIDER` config (Phase 6: EMBED-01..02).
- Production hardening of latency budgets and audit logging (Phase 6: PERF-02..04, OBS-02..03 finalization).
- Cross-provider failover for fuzzy/scan calls (provider failure today triggers algorithmic-fallback or skip per D-78; bidirectional crossover ships in Phase 6).
- Output-side filter on cloud LLM responses (PRD does not require it; carries forward from Phase 3 deferral).
- Title generation / metadata extraction migration onto `LLMProviderClient` (Phase 5–6).
- Phrasebook expansion of the prompt-guidance helper into Indonesian (D-81 locks English-only for v1.0).

</domain>

<decisions>
## Implementation Decisions

### Fuzzy De-anonymization — Algorithm, Library, Threshold, Normalization

- **D-67 (DEANON-03, FR-5.4):** **`rapidfuzz` library for Jaro-Winkler.** Use `rapidfuzz.distance.JaroWinkler.normalized_similarity(s1, s2)` (returns 0.0–1.0; matches Phase 2 D-29 score normalization). Already a transitive dependency of Presidio (no new top-level dep added to `requirements.txt`); C-extension speed; well-maintained; matches PRD FR-5.4 algorithm choice. Rejected: `python-Levenshtein` (different algorithm; less linguistically appropriate for proper-name fuzziness), `jellyfish` (pure-Python; ~50× slower at warm-path scale), custom implementation (reinventing a battle-tested library).

- **D-68 (DEANON-03):** **Per-cluster variant scoping for fuzzy matching.** Fuzzy candidates come exclusively from the cluster's variant rows already written by Phase 3 D-48 (canonical + first-only + last-only + honorific-prefixed + nickname). The matcher scores `mangled_text` against each variant in the registry; the highest score wins if it clears the threshold. Rejected: cross-cluster scoring (could merge two distinct people whose surrogate names happen to be similar — corruption risk), full-thread token-bag (scales poorly and produces ambiguous matches), only-canonical scoring (misses Phase 3's sub-surrogate variants — defeats D-48's whole purpose).

- **D-69 (DEANON-03, PROVIDER-06):** **Single `FUZZY_DEANON_THRESHOLD` env var, default `0.85`, also exposed as `system_settings.fuzzy_deanon_threshold`.** PRD-mandated default (FR-5.4 specifies "≥ 0.85"). Numeric column with CHECK `>= 0.50 AND <= 1.00` (defense-in-depth — Pydantic Literal/range validator at the API layer, DB CHECK at the data layer; matches Phase 3 D-57 pattern). Reads via existing `get_system_settings()` 60s TTL cache (Phase 2 D-21 / SET-01). Rejected: per-mode thresholds (no PRD evidence two thresholds are needed; doubles config surface), hard-coded constant (loses runtime tunability that ops will want for tuning).

- **D-70 (DEANON-03):** **Pre-fuzzy normalization: strip honorifics + casefold + token-level scoring.** Before invoking Jaro-Winkler:
  1. Strip honorifics using Phase 1's `honorifics.py` constant set (Pak, Bu, Bapak, Ibu, Mr., Ms., Dr., etc.).
  2. `.casefold()` both strings (consistent with Phase 2 D-36's casefold invariant + Phase 3 D-53's egress-filter casefold).
  3. Token-level scoring: split into whitespace tokens, score each token against each variant token, take max.
  
  This ensures "pak Smith" vs registry's `Pak Smith` matches at 1.0 (after honorific normalization) instead of being rejected as a near-miss. Rejected: word-bag/Jaccard pre-step (Jaro-Winkler already handles partial matches), full-string scoring without tokenization (misses "John A. Smith" vs "John Smith" cases — token-level scoring catches them).

### 3-Phase Pipeline Integration

- **D-71 (DEANON-04, FR-5.4):** **In-place upgrade of `de_anonymize_text` with optional `mode` parameter.** Extend the Phase 2 method signature:

  ```python
  async def de_anonymize_text(
      self,
      text: str,
      registry: ConversationRegistry,
      mode: Literal['algorithmic', 'llm', 'none'] | None = None,
  ) -> str:
      ...
  ```

  When `mode is None`, resolve via env (`FUZZY_DEANON_MODE`) → `system_settings.fuzzy_deanon_mode` → default `none`. Default `none` keeps every Phase 2 test green. The Phase 2 D-34 docstring already promised this in-place extension ("Phase 4 will insert its placeholder-tokenized fuzzy-match pass BETWEEN the existing two passes ... without rewriting this call site"). Rejected: new method `de_anonymize_text_v2` (forces every Phase 2 caller to be hand-migrated), service-level dispatcher (adds a layer for no benefit).

- **D-72 (DEANON-04):** **Mode dispatch resolved in service, fuzzy LLM path called via `LLMProviderClient`.** Inside `de_anonymize_text`:
  - Read effective `mode` (param → env → DB → default `none`).
  - For `algorithmic`: invoke local `_fuzzy_match_algorithmic(remaining_text, registry)` (uses D-67 rapidfuzz logic).
  - For `llm`: invoke `await llm_provider.call(feature='fuzzy_deanon', messages=..., registry=registry, provisional_surrogates=None)` — the call sees ONLY placeholder-tokenized text per D-73; the egress filter from Phase 3 D-53..D-56 still runs as a defense-in-depth backstop.
  - For `none`: skip Pass 2 entirely; behavior identical to Phase 2.
  
  Rejected: routing in `LLMProviderClient` (mixes resolution policy with transport; loses the algorithmic path entirely from the client), separate `FuzzyResolver` class (premature abstraction; one conditional in one method is clearer).

- **D-73 (DEANON-04, NFR-2):** **LLM payload = placeholder-tokenized text in, JSON `[{span, token}]` mappings out.** For `mode='llm'`:
  - **Input messages:** Pass 1's output (text where every known surrogate is already replaced by `<<PH_xxxx>>`) + a JSON list of cluster variants like `[{token: '<<PH_0001>>', canonical: 'Marcus Smith', variants: ['M. Smith', 'Marcus', 'Pak Smith']}, ...]`.
  - **Output (Pydantic-validated):** `{matches: [{span: 'M. Smyth', token: '<<PH_0001>>'}, ...]}`. Server resolves spans to positions via `re.escape(span)` substring search (matches D-77's "let server do positions" rationale).
  - **Privacy invariant:** the cloud LLM sees zero raw real values. Placeholder-tokenized text + variant list (which contains canonical surrogate names + their cluster sub-variants — all surrogate-form, already safe per Phase 1 invariants).
  - The pre-flight egress filter (Phase 3 D-53..D-56) still runs against the message payload as a defense-in-depth check.
  
  Rejected: send raw text to LLM (defeats the placeholder-tokenization invariant — privacy regression), boolean classifier per cluster (loses per-mention granularity — multiple mangled surrogates in same cluster need distinct matches).

- **D-74 (DEANON-05, REG-05):** **Hard-redact survival inherited from Phase 2 D-24.** Hard-redact placeholders (`[CREDIT_CARD]`, `[US_SSN]`, etc.) are NEVER written into the registry per Phase 2 REG-05 / D-24. Therefore Pass 1 (surrogate→placeholder replacement) cannot match them; Pass 2 (fuzzy matching) operates only on cluster variants from the registry — also cannot match `[CREDIT_CARD]`; Pass 3 (placeholder→real resolution) only knows about Pass 1's `<<PH_xxxx>>` form, not `[TYPE]`. Hard-redact placeholders pass through all three passes unmodified. Add an explicit assertion test across all 3 modes (`algorithmic`, `llm`, `none`) confirming `[CREDIT_CARD]` survives in each. Rejected: explicit hard-redact filtering pass (redundant — invariant is already structural), runtime regex check for `\[[A-Z_]+\]` patterns (false positives on legal-doc citations like "[CONTRACT]").

### Missed-PII Scan — Placement, Re-NER Scope, Schema, Soft-Fail

- **D-75 (SCAN-01..03, FR-8.1..3):** **Auto-chain inside `RedactionService.redact_text`.** Pipeline becomes: detect (Presidio) → anonymize (Phase 1 D-12 surrogate generation + clustering D-45) → missed-scan (NEW) → re-anonymize-if-replaced → return. Gated by `PII_MISSED_SCAN_ENABLED` (column already shipped in Phase 3 migration 030 D-57). The scan operates on the **already-anonymized** text per FR-8.1, so the input to the cloud LLM is just surrogates + `[TYPE]` placeholders — privacy-safe by construction. Existing Phase 2 callers and Phase 5 chat-loop integration get the scan for free with no extra wiring. Rejected: separate `scan_for_missed_pii` method requiring caller invocation (adds a wiring concern Phase 5 must remember; risk of forgotten calls in sub-agent paths), output-side scan only (FR-8.1 explicitly targets PII the primary NER missed on input).

- **D-76 (SCAN-05, FR-8.5):** **Full re-run of `redact_text` on modified text when scan replaces entities.** Treat post-replacement text as a fresh input — re-detect via Presidio, re-anchor existing surrogates by registry lookup (D-48 variants compose), re-emit anonymized output. Simplest, most correct, position-safe. Bookkeeping for partial NER reruns (around scan-replaced spans only) is fragile and missed-scan replacements are rare on a typical chat message — the perf cost of full re-run is an acceptable tax for the simplicity. Re-run is bounded: if the second pass also flags missed entities, do NOT loop a third time (single re-run cap) — log the second-pass entities at WARNING and skip another re-run to prevent unbounded recursion. Rejected: localized NER re-run around replaced spans (complex position bookkeeping), no re-run trust-the-scan (PRD FR-8.5 explicitly mandates re-run; surrogate positions in downstream registry writes would drift).

- **D-77 (SCAN-04, FR-8.4):** **LLM scan response schema: `[{type, text}]` pairs; server substring-matches via `re.escape`.** Pydantic model:

  ```python
  class MissedEntity(BaseModel):
      type: str  # validated against settings.PII_HARD_REDACT_ENTITIES; invalid types dropped
      text: str  # validated as non-empty, len < 1000
  
  class MissedScanResponse(BaseModel):
      entities: list[MissedEntity]
  ```

  Server then iterates: for each `MissedEntity`, run `re.finditer(re.escape(text), anonymized_text)` to find ALL occurrences (handles multi-mention) → replace each with `[<TYPE>]` hard-redact placeholder. LLMs are unreliable at character-offset arithmetic (lesson from Phase 1 B2 grep false positive — whitespace and tokenization quirks shift positions); substring search is forgiving. Rejected: full positional info `{type, text, start, end}` (one-char drift corrupts surrounding text — high blast radius), boolean classifier per type (loses the actual matched text — server has to re-scan with type-specific regex, doubles the round-trip work).

- **D-78 (PERF-04, NFR-3, OBS-02):** **Soft-fail with warn-log + `@traced` span tag + counter metric.** When the scan provider is unavailable (timeout / 5xx / network error / Pydantic validation failure):
  - Log at WARNING: `{"event":"missed_scan_skipped", "feature":"missed_scan", "provider":"<resolved>", "error_class":"<TimeoutError|HTTPError|ValidationError>", "reason":"<one-line>"}`. Never log raw payloads or PII per B4.
  - Tag the `@traced(name='redaction.missed_scan')` span: `scan_skipped=true`, `scan_skipped_reason=<error_class>`, `scan_provider=<resolved>`.
  - Increment a counter metric `pii_missed_scan_skipped_total{reason}` (Prometheus/StatsD style; observability skill TBD by ops — Phase 6 hardens).
  - Anonymization continues with primary NER results only. PRD PERF-04 explicitly mandates this "skipped, never crash, never leak" behavior.
  
  Rejected: hard-fail (contradicts PERF-04 and breaks chat flow when LLM provider is flaky), hard-fail-cloud-only (privacy-strict reading; would need a PRD amendment), warn-log only without metrics (ops can't see scan health over time).

### System-Prompt Guidance — Site, Conditionality, Language, Content

- **D-79 (PROMPT-01, FR-7):** **Centralized helper module — `backend/app/services/redaction/prompt_guidance.py` — appended in both `chat.py` and `agent_service.py`.** Module exposes:

  ```python
  def get_pii_guidance_block(*, redaction_enabled: bool) -> str:
      """Returns the surrogate-preservation prompt block, or empty string if redaction is off."""
  ```

  Caller pattern (chat.py):
  ```python
  system_prompt = SYSTEM_PROMPT + get_pii_guidance_block(redaction_enabled=thread.redaction_enabled)
  ```

  And in `agent_service.py`, each of the 4 agent definitions (General, Research, Compare, Compliance — lines 11/29/49/64) calls the same helper at agent-construction time. Single source of truth; covers main-agent (chat completions) AND sub-agent paths (Phase 5's TOOL-01..04 carry-forward). Module sits alongside `honorifics.py`, `nicknames_id.py`, `gender_id.py` — same "small focused module per concern" Phase 1 pattern. Rejected: only `chat.py` (sub-agents won't preserve surrogates → DEANON-03 fails for tool/sub-agent flows), only `agent_service.py` (chat.py main-agent path needs duplicate inline copy — fragile when prompts evolve), separate copies in each callsite (drift inevitable).

- **D-80 (PROMPT-01):** **Conditional injection — only when redaction is enabled for the thread.** Helper returns `""` (empty string) when `redaction_enabled=False`. Why: when redaction is off, no surrogates exist in the user's message; instructing the LLM to "preserve names verbatim" is dead weight that adds tokens and confusion. Thread-level flag is cheap (already loaded with the thread row). Rejected: always inject (~150 tokens of dead weight per non-redaction request), registry-count-conditional (per-message DB check on the system-prompt build path — too expensive for the marginal savings on early turns of redaction-on threads).

- **D-81 (PROMPT-01):** **English-only phrasing.** System-prompt instruction blocks are most reliable in English across all LLM providers in the LexCore stack (OpenRouter/OpenAI for production chat, LM Studio/Ollama for local privacy mode). Indonesian user content + English system instructions is the standard LexCore pattern that already works for the existing tool-calling logic. Rejected: Indonesian-first (weaker compliance on smaller local models that are English-dominant in instruction-following training data; ~2× block length), bilingual (~2× tokens per turn for marginal compliance gain).

- **D-82 (PROMPT-01, DEANON-05):** **Imperative rules + explicit type list + `[TYPE]` warning + 1-2 concrete examples.** Block content (~150 tokens):

  ```
  CRITICAL: Some text in this conversation may contain placeholder values that look like real names, emails, phones, locations, dates, URLs, or IP addresses. You MUST reproduce these EXACTLY as written, with NO abbreviation, NO reformatting, and NO substitution. Treat them as opaque tokens.

  Specifically: when you see text like "John Smith", "user@example.com", "+62-21-555-1234", "Jl. Sudirman 1", "2024-01-15", "https://example.com/x", or "192.168.1.1" in the input, output it character-for-character identical. Do NOT shorten "John Smith" to "J. Smith" or "Smith". Do NOT reformat "+62-21-555-1234" to "+622155512345".

  Additionally, ANY text wrapped in square brackets like [CREDIT_CARD], [US_SSN], or [PHONE_NUMBER] is a literal placeholder — preserve it exactly, do not replace it with a fabricated value.

  Examples:
  - Input contains "Marcus Smith" → output "Marcus Smith" (NOT "Marcus" or "M. Smith" or "Mark Smith")
  - Input contains "[CREDIT_CARD]" → output "[CREDIT_CARD]" (NOT "credit card number" or a fabricated number)
  ```

  Strict imperative ("MUST", "NEVER") + explicit Phase-1-supported types + dual coverage of surrogates AND hard-redact placeholders + concrete examples. Examples are the highest-leverage element for instruction compliance — RLHF-trained LLMs follow examples more reliably than abstract rules. Rejected: rules + type list without examples (~80 tokens; weaker compliance — examples are load-bearing), soft prose ("please preserve..."; RLHF interprets "please" as optional — invariant violation risk).

</decisions>

<carry_forward>
## Carry-Forward From Phases 1–3

The following load-bearing decisions from prior phases are preconditions for Phase 4. Planning and execution must respect them.

### From Phase 1 (Detection & Anonymization Foundation)
- **D-12** Faker surrogate generation (gender-matched, collision-free) — produces the surrogate strings that Phase 4's fuzzy matcher operates against.
- **D-16** `@traced(name="...")` decorator pattern (LangSmith/Langfuse pluggable) — Phase 4 reuses for `redaction.de_anonymize_text`, `redaction.fuzzy_match`, `redaction.missed_scan`.
- **B4 invariant** — never log raw PII (counts/timings/hashes only). D-78's soft-fail logging strictly adheres.
- **`honorifics.py`** — D-70's pre-fuzzy normalization imports and reuses this constant set.

### From Phase 2 (Conversation-Scoped Registry & Round-Trip)
- **D-21 / SET-01** `get_system_settings()` 60s TTL cache — Phase 4's new `fuzzy_deanon_mode` and `fuzzy_deanon_threshold` columns flow through this cache; admin UI changes propagate within the TTL window (carries forward Phase 3 SC#5).
- **D-24 / REG-05** Hard-redact placeholders are never written to the registry — load-bearing for D-74 (hard-redact survival).
- **D-27** `entity_registry` `casefold()`-keyed `O(1)` lookup — Phase 4's Pass 1 surrogate→placeholder replacement reuses this hot path.
- **D-32** INSERT-ON-CONFLICT-DO-NOTHING upsert — composes with Phase 4's missed-scan re-run (D-76); existing surrogates re-anchor without DB churn.
- **D-34** 1-phase placeholder-tokenized round-trip (DEANON-01/02) with forward-compat docstring — D-71's in-place extension follows this contract verbatim.
- **D-36** `casefold()` invariant — D-70's pre-fuzzy normalization preserves the invariant; D-77's `re.escape` substring search runs on un-casefolded text per the registered surrogate's casing.
- **D-37** Cross-turn forbidden tokens — composes with Phase 4 D-68 per-cluster scoping; the variant set used by fuzzy matching is the same set used to seed forbidden tokens.

### From Phase 3 (Entity Resolution & LLM Provider Configuration)
- **D-45** Pre-generation Union-Find clustering for PERSON entities — produces the canonical surrogate per cluster that D-68's fuzzy matcher uses as the anchor.
- **D-48** Sub-surrogate variant rows at registry-write time (canonical + first-only + last-only + honorific-prefixed + nickname) — D-68 fuzzy matching scopes against exactly this variant set; D-73's LLM-mode JSON variant list is built from these rows.
- **D-49** `LLMProviderClient.call(feature, messages, registry, provisional_surrogates)` — D-72 invokes this directly for `feature='fuzzy_deanon'`; D-75 invokes this directly for `feature='missed_scan'`. Both `feature` strings are already in the Literal type per Phase 3 D-49.
- **D-51** Per-feature provider override resolution (env → DB → global env → global DB → default `local`) — Phase 4's fuzzy and missed-scan calls inherit this resolution stack via `fuzzy_deanon_llm_provider` and `missed_scan_llm_provider` columns (already shipped in Phase 3 D-57 migration 030).
- **D-52** `LLM_PROVIDER_FALLBACK_ENABLED` knob (default false) + algorithmic-fallback path on cloud failure — Phase 4 fuzzy LLM-mode failure falls back to algorithmic fuzzy mode if the knob is on; missed-scan failure falls back to skip-with-warn (D-78) regardless.
- **D-53..D-56** Pre-flight egress filter — runs on every cloud-mode call from `LLMProviderClient`. Phase 4's fuzzy LLM-mode and missed-scan calls inherit this defense-in-depth backstop. Filter scope = persisted registry + in-flight provisional surrogates (Phase 4 missed-scan has no provisional set; passes `provisional_surrogates=None`).
- **D-57** `system_settings` columns shipped in migration 030: `pii_missed_scan_enabled`, `fuzzy_deanon_llm_provider`, `missed_scan_llm_provider`. Phase 4 migration 031 ADDS `fuzzy_deanon_mode` + `fuzzy_deanon_threshold`. No conflict.
- **D-65 / D-66** `LLMProviderClient` unit suite + egress-filter exhaustive matrix — Phase 4 reuses these test fixtures (mocked `AsyncOpenAI`, mocked `_get_client`) for `feature='fuzzy_deanon'` and `feature='missed_scan'` paths.

</carry_forward>

<schema_changes>
## Schema & Configuration Changes

### Migration 031: `031_pii_fuzzy_settings.sql`

Adds two columns to the existing single-row `system_settings` table:

```sql
ALTER TABLE system_settings
  ADD COLUMN fuzzy_deanon_mode text NOT NULL DEFAULT 'none'
    CHECK (fuzzy_deanon_mode IN ('algorithmic', 'llm', 'none')),
  ADD COLUMN fuzzy_deanon_threshold numeric(3,2) NOT NULL DEFAULT 0.85
    CHECK (fuzzy_deanon_threshold >= 0.50 AND fuzzy_deanon_threshold <= 1.00);
```

Defense-in-depth: Pydantic `Literal['algorithmic', 'llm', 'none']` + numeric range validator at the API layer; DB CHECK at the data layer (Phase 3 D-57 pattern).

### New Environment Variables

| Var | Default | Purpose |
|---|---|---|
| `FUZZY_DEANON_MODE` | `none` | Override `system_settings.fuzzy_deanon_mode`. Values: `algorithmic` / `llm` / `none`. |
| `FUZZY_DEANON_THRESHOLD` | `0.85` | Override `system_settings.fuzzy_deanon_threshold`. Range: `[0.50, 1.00]`. |

Both flow through `backend/app/config.py` (Pydantic Settings); both are admin-UI editable via the existing PATCH endpoint on `/admin/settings`.

### Existing Environment Variables (No Change, Used by Phase 4)
- `PII_MISSED_SCAN_ENABLED` (Phase 3 migration 030 D-57; default `true`).
- `MISSED_SCAN_LLM_PROVIDER` / `FUZZY_DEANON_LLM_PROVIDER` (Phase 3 D-57; per-feature override; falls back to `LLM_PROVIDER`).
- `LLM_PROVIDER` / `LOCAL_LLM_BASE_URL` / `LOCAL_LLM_MODEL` / `CLOUD_LLM_BASE_URL` / `CLOUD_LLM_MODEL` / `CLOUD_LLM_API_KEY` / `LLM_PROVIDER_TIMEOUT_SECONDS` / `LLM_PROVIDER_FALLBACK_ENABLED` (Phase 3).
- `PII_HARD_REDACT_ENTITIES` (Phase 1; D-77 validates missed-scan responses against this set).

</schema_changes>

<files_touched>
## Files to Create / Modify

### NEW
- `backend/app/services/redaction/fuzzy_match.py` — Algorithmic Jaro-Winkler matcher (D-67, D-68, D-70). Pure function; no DB; no SDK. Imports `rapidfuzz.distance.JaroWinkler` and `honorifics` constants.
- `backend/app/services/redaction/missed_scan.py` — LLM-based missed-PII scan logic (D-75, D-77, D-78). Calls `LLMProviderClient.call(feature='missed_scan', ...)`. Pydantic `MissedScanResponse` model. Server-side `re.escape` substring-match resolution.
- `backend/app/services/redaction/prompt_guidance.py` — `get_pii_guidance_block(*, redaction_enabled: bool) -> str` (D-79, D-80, D-81, D-82). Module-level constant `_GUIDANCE_BLOCK` holds the imperative rules + examples.
- `supabase/migrations/031_pii_fuzzy_settings.sql` — `fuzzy_deanon_mode` + `fuzzy_deanon_threshold` columns.
- `backend/tests/unit/test_fuzzy_match.py` — D-67/D-68/D-70 algorithmic matcher coverage; honorific-stripped equality, casefold equality, threshold boundary, per-cluster scoping.
- `backend/tests/unit/test_missed_scan.py` — D-75/D-77/D-78 schema validation, hard-redact-set filtering, soft-fail behavior on mocked `LLMProviderClient` failures.
- `backend/tests/unit/test_prompt_guidance.py` — D-79/D-80/D-82 helper output (redaction on vs off, content assertions: type list, `[TYPE]` warning, examples).
- `backend/tests/api/test_phase4_integration.py` — ROADMAP SC#1..SC#5 end-to-end. Live Supabase + mocked cloud SDK; mirrors Phase 3's `test_resolution_and_provider.py` pattern.

### MODIFY
- `backend/app/services/redaction_service.py` — Extend `de_anonymize_text` with optional `mode` parameter (D-71); insert Pass 2 fuzzy-match step (D-72); auto-chain missed-scan inside `redact_text` with full re-run on replacement (D-75, D-76).
- `backend/app/config.py` — Add `FUZZY_DEANON_MODE` + `FUZZY_DEANON_THRESHOLD` Pydantic Settings fields with validators.
- `backend/app/routers/admin_settings.py` — Add `fuzzy_deanon_mode` and `fuzzy_deanon_threshold` to the PATCH/GET payload schema for `/admin/settings`.
- `backend/app/routers/chat.py` — Append `get_pii_guidance_block(redaction_enabled=...)` to SYSTEM_PROMPT at chat-completion-build time (D-79).
- `backend/app/services/agent_service.py` — Append `get_pii_guidance_block(redaction_enabled=...)` to each of the 4 agent `system_prompt` definitions at agent-construction time (D-79).
- `frontend/src/pages/admin/SettingsPage.tsx` (or equivalent admin UI page) — Add fuzzy-mode dropdown (`algorithmic` / `llm` / `none`) + threshold slider (`0.50`–`1.00`, step `0.05`) to the existing "PII Redaction & Provider" section.

### REFERENCE (Read, Not Modified)
- `backend/app/services/llm_provider.py` — Phase 3's `LLMProviderClient`. `feature='fuzzy_deanon'` and `feature='missed_scan'` are already in the Literal type per D-49.
- `backend/app/services/redaction/honorifics.py` — D-70 imports honorific constants.
- `backend/app/services/redaction/clustering.py` — D-68 sources cluster variant sets (Phase 3 D-48 sub-surrogate rows are written here).
- `backend/app/services/redaction/registry.py` — D-72/D-77 read variants; D-76 re-anchors on full re-run.

</files_touched>

<success_criteria>
## Success Criteria → Test Mapping

| ROADMAP SC | What it tests | Primary test |
|---|---|---|
| **SC#1** Mangled-surrogate de-anon resolves correctly under `algorithmic`/`llm`; passes through under `none` | D-67/D-68/D-70 matching + D-71/D-72 mode dispatch | `test_phase4_integration.py::TestSC1_FuzzyDeanon` (3 subtests: surname dropped, casing flipped, one-char typo — each across 3 modes) |
| **SC#2** 3-phase pipeline prevents surname-collision corruption | D-71 placeholder tokenization isolates clusters; D-68 per-cluster variant scoping | `test_phase4_integration.py::TestSC2_NoSurnameCollision` (two clusters share surname; only correct one resolves) |
| **SC#3** Hard-redact `[TYPE]` placeholders survive de-anonymization in every mode | D-74 inherited from D-24/REG-05 | `test_phase4_integration.py::TestSC3_HardRedactSurvives` (3 subtests across modes; assertion on identity preservation) |
| **SC#4** With `PII_MISSED_SCAN_ENABLED=true`, scan runs across all 3 resolution modes; invalid types discarded; primary NER re-runs after replacement | D-75/D-76/D-77 | `test_phase4_integration.py::TestSC4_MissedScan` (3 subtests across resolution modes; mocked LLM returns valid + invalid types; assertion on filter + re-NER) |
| **SC#5** Main-agent system prompt instructs LLM to reproduce surrogates verbatim; e2e test shows surrogates emitted in exact source format | D-79/D-80/D-81/D-82 helper + chat completion path | `test_phase4_integration.py::TestSC5_VerbatimEmission` (mocked OpenRouter; assertion that returned response contains exact-form surrogates from input) |

Bonus coverage:
- `TestB4_LogPrivacy_FuzzyAndScan` — extends Phase 1 B4 / Phase 2-3 caplog invariants to D-78's missed-scan soft-fail logs.
- `TestSoftFail_ProviderUnavailable` — mocked `LLMProviderClient.call` raises; assertions on warn-log content + span tag + counter increment + anonymization-still-completes (D-78).

</success_criteria>

<dependencies>
## Phase Dependencies

**Hard preconditions (must already be true; verified pre-planning):**
- Phase 3 SHIPPED ✓ (verified 2026-04-26): `LLMProviderClient`, `feature` Literal includes `fuzzy_deanon` + `missed_scan`, pre-flight egress filter, `system_settings` columns from migration 030.
- Phase 1 SHIPPED ✓: `honorifics.py`, Faker surrogate generation, `@traced` decorator, B4 log-privacy invariant.
- Phase 2 SHIPPED ✓: registry casefold-keyed lookup, INSERT-ON-CONFLICT upsert, `de_anonymize_text` v1 with forward-compat docstring, hard-redact NEVER in registry invariant.

**Soft preconditions (can be assumed by tests / docs):**
- Live Supabase project `qedhulpfezucnfadlfiz` available for integration tests (Phase 3 `test_resolution_and_provider.py` already wires this).
- `rapidfuzz` is reachable via `pip show rapidfuzz` (transitive Presidio dep — verify in Plan 04-01 acceptance check; if absent, promote to direct top-level dep in `requirements.txt`).

**What Phase 4 unblocks:**
- Phase 5 (chat-loop integration): the `redact_text` and `de_anonymize_text` methods now match the production-grade contract Phase 5 needs to wire through chat completions, sub-agents, and tool-result preprocessing. Phase 5's TOOL-01..04 simply imports `get_pii_guidance_block` for sub-agent prompts.
- Phase 6 (production hardening): the prompt-guidance + missed-scan instrumentation surfaces the OBS-02/03 audit-log fields Phase 6 will surface in Railway / LangSmith dashboards.

</dependencies>

<open_questions>
## Open Questions Deferred to Planner

The planner (`gsd-planner`) will resolve these during plan generation; they are not architectural gray areas:

- Plan boundaries — likely 5–7 plans matching Phase 3's cadence: (01) migration 031 + config; (02) `fuzzy_match.py` algorithmic; (03) `de_anonymize_text` 3-phase upgrade including LLM mode; (04) `missed_scan.py` + `redact_text` auto-chain + re-NER; (05) `prompt_guidance.py` + chat.py + agent_service.py wiring; (06) admin UI extension; (07) integration test suite.
- Per-plan dependency wave assignments (Phase 1 used 4 waves, Phase 3 used 6 waves — Phase 4 likely 3–4).
- Specific test-fixture seeds for SC#1's "slightly-mangled surrogate" cases (the planner picks deterministic seeds).
- Performance budgets: D-67 rapidfuzz is C-extension; expected impact <5ms per turn at typical surrogate counts. Hard target ships in Phase 6 PERF-02 finalization. Plan 04 verification is functional, not latency-bound.
</open_questions>
