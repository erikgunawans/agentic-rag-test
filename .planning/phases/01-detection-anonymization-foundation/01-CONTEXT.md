# Phase 1: Detection & Anonymization Foundation - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship the always-on detection-and-substitution layer so any text passing through the new redaction service yields realistic, gender-matched, collision-free Indonesian-locale surrogates without leaking real values into logs.

In scope:
- New `RedactionService` (`backend/app/services/redaction_service.py`) with a single async public method that detects PII via Presidio + spaCy, substitutes surrogate-bucket entities with Faker `id_ID` values, and replaces hard-redact-bucket entities with `[ENTITY_TYPE]` placeholders.
- Pluggable observability layer (`TRACING_PROVIDER=langsmith|langfuse|none`) replacing the current hardcoded LangSmith wiring.
- Lazy `@lru_cache` singletons (Presidio NER engine, gender detector, nickname dictionary) eagerly warmed in FastAPI `lifespan` for first-request hot path.
- Pure pytest test suite that imports `RedactionService` directly.

Explicitly NOT in scope (deferred to later phases):
- Conversation-scoped persistence of real → surrogate mappings (Phase 2: REG-01..05).
- Round-trip de-anonymization of LLM output (Phase 2: DEANON-01..02; Phase 4: DEANON-03..05).
- Entity resolution (algorithmic / LLM clustering of name variants — Phase 3).
- LLM provider switch (`LLM_PROVIDER`) and pre-flight egress filter (Phase 3).
- Chat-loop integration: SSE buffering, status events, tool/sub-agent symmetric coverage (Phase 5).
- HTTP API surface for redaction (chat integration is Phase 5; no `/admin/redaction/test` endpoint in Phase 1).

</domain>

<decisions>
## Implementation Decisions

### NER Model & Indonesian Coverage
- **D-01 (PII-01, PII-02):** Use **`xx_ent_wiki_sm`** as the spaCy NLP engine fed into Presidio. Multilingual, ~12 MB, recognizes Indonesian person names ("Bambang Sutrisno", "Sri Mulyani") more reliably than `en_core_web_*`. Acceptable accuracy/cost tradeoff for an Indonesian-default product on Railway. Rejected: `en_core_web_trf` (English-biased — misclassifies Indonesian names), hybrid two-model ensemble (~2x latency, Railway memory pressure), `id_core_news_lg` (weaker on English entities common in legal text).
- **D-02 (PII-04):** Pre-process input with an **honorific strip-and-reattach** pass before NER. Recognized prefixes: `Pak`, `Bapak`, `Bu`, `Ibu`, `Sdr.`, `Sdri.` (case-insensitive, word-boundary-anchored). Honorific is held aside, NER runs on the bare name, surrogate is rebuilt as `<honorific> <surrogate-name>`. Improves detection accuracy and preserves cultural register in surrogates ("Pak Bambang" → "Pak Joko Wijaya", not "Marcus Smith").
- **D-03 (PII-05):** Honour PRD defaults `PII_SURROGATE_SCORE_THRESHOLD=0.7` and `PII_REDACT_SCORE_THRESHOLD=0.3`. Both exposed as env vars on `Settings`. Per-entity-type thresholds deferred to Phase 6 hardening (would inflate env-var surface without eval data to justify it).

### Faker Surrogates
- **D-04 (ANON-01, ANON-04):** **Faker(`id_ID`) only** for all surrogate-bucket entities (PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION, DATE_TIME, URL, IP_ADDRESS). Indonesian phone format (+62), Indonesian cities, Indonesian person-name pool. Foreign names in chat inputs also receive Indonesian surrogates — accepted as a cultural-consistency tradeoff. Locale auto-detect rejected (extra `langdetect` call per entity, latency hit).
- **D-05 (ANON-04):** Gender-matched surrogates. **Note for planner:** the `gender-guesser` library is English-biased; Indonesian-name gender detection is unreliable. Phase 1 ships `gender-guesser` for English fallback PLUS a small hand-curated Indonesian first-name → gender lookup table seeded from common Indonesian names (Bambang, Budi, Joko = M; Sri, Siti, Dewi = F; ambiguous → random). Lookup table lives under `backend/app/services/redaction/gender_id.py`. Expand over time.
- **D-06 (ANON-03):** **10-retry collision budget** with non-realistic fallback. After 10 failed Faker attempts, emit `[PERSON_<6-char-hash>]` (or `[EMAIL_<hash>]`, etc.) — distinct from hard-redact placeholders so de-anon (Phase 2) can still round-trip if the real value is in registry. Bounded latency under pathological inputs.
- **D-07 (ANON-05):** **Strict surname / first-name cross-check** per FR-2.5. Maintain a per-call set of all real first-name and surname tokens (extracted via `nameparser`); reject any Faker output whose tokens overlap. Prevents the surname-collision corruption scenario (PRD §7.5). Logging of rejections deferred to Phase 6 to avoid log noise.
- **D-08 (ANON-02):** **Same `[ENTITY_TYPE]` placeholder for all instances** of a hard-redact type within a single redaction call. Two credit cards in one input both render as `[CREDIT_CARD]`. Matches PRD literal wording and keeps Phase 1 simple. Numbered placeholders (`[CREDIT_CARD_1]`, `[CREDIT_CARD_2]`) deferred — can revisit if user feedback demands disambiguation.

### UUID False-Positive Filter
- **D-09 (PII-04):** **Pre-input mask + post-NER restore** strategy. Step 1: regex-find all UUIDs in input, replace with sentinel tokens `<<UUID_0>>`, `<<UUID_1>>`, … Step 2: run Presidio NER on the masked text (zero chance NER touches UUIDs). Step 3: after anonymization, replace sentinels back with original UUIDs. Bulletproof — chosen over post-NER span-overlap drop because Presidio span boundaries are sometimes off-by-one on adjacent tokens.
- **D-10:** **Standard 8-4-4-4-12 hex** UUID regex (`[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}`, case-insensitive). Covers Supabase/Postgres `uuid_generate_v4()` output. Bare 32-hex and numeric IDs rejected to avoid false-positive-masking phone numbers and bank account numbers (which SHOULD be redacted).
- **D-11:** **Sentinel collision check** — before pre-masking, scan input for any literal `<<UUID_` substring; if present, fail fast with a `RedactionError` rather than silently corrupting. Pathological but cheap insurance.
- **D-12:** Phase 1's redaction service operates on **plain text only** — no structured tool-arg awareness. Tool-arg `document_id` field protection is Phase 5 (TOOL-01..04). Keeps Phase 1 API focused.

### Service API Shape
- **D-13:** Public API is **`async def redact_text(text: str) -> RedactionResult`** — single async method on a `RedactionService` class instance accessed via `get_redaction_service()` (`@lru_cache`'d singleton getter). `RedactionResult` is a Pydantic model with: `anonymized_text: str`, `entity_map: dict[str, str]` (real → surrogate, no hard-redacted entries), `hard_redacted_count: int`, `latency_ms: float`. Internal helpers (`_detect`, `_anonymize`, `_apply_uuid_mask`) remain private; future phases re-expose them only if needed.
- **D-14:** Phase 1's `redact_text()` is **stateless** — no thread/conversation/registry parameter. Phase 2 will widen the signature to `redact_text(text, registry: ConversationRegistry | None = None)`. Phase 1 callers get fresh in-memory state per call.

### Initialization Pattern
- **D-15 (PERF-01):** **`@lru_cache`'d singleton getters** for Presidio NER engine, gender detector, nickname dictionary, Faker(`id_ID`) instance — AND eager warm-up in FastAPI `lifespan` at startup. Satisfies both Phase 1 SC#5 ("lazy-singleton") and PRD NFR-1 ("loaded once at startup"). First real chat request after deploy is hot. `lifespan` calls `get_redaction_service()` once and discards the return value.

### Tracing & Observability
- **D-16 (OBS-01):** **Full pluggable `TRACING_PROVIDER`** abstraction shipped in Phase 1. `langsmith_service.py` is renamed `tracing_service.py` and exposes a `@traced(name=...)` decorator that switches at import time based on `TRACING_PROVIDER` env var (`langsmith` | `langfuse` | empty). Empty value → no-op decorator (zero overhead). Both `langsmith.traceable` and `langfuse.observe` have similar signatures — the shim wraps whichever is configured.
- **D-17:** Phase 1 ships **both langsmith and langfuse adapters** (langfuse-python is a small dep). Defers no migration debt to Phase 6. Existing `@traceable(name=...)` call sites across the codebase migrate to the new `@traced` import in the same Phase 1 commit.
- **D-18:** All redaction operations (full `redact_text` call + internal `_detect`, `_anonymize`, `_apply_uuid_mask` if non-trivial) are wrapped in `@traced(name="redaction.<op>")`. Span attributes include: input length, entity counts per type (without values), surrogate count, hard-redact count, UUID-filter drops, total latency. **Never log real values.**

### Testing
- **D-19:** **Pure pytest unit tests** at `backend/tests/api/test_redaction.py` (despite the `api/` dir name — matches existing convention) and a new `backend/tests/unit/test_redaction_service.py` if needed. Imports `RedactionService` directly; no HTTP. Test cases cover all five Phase 1 success criteria — Indonesian-name detection, two-pass thresholds, UUID survival, gender-matched surrogates, lazy-singleton reuse.
- **D-20:** **Faker `seed_instance(seed)`** is called per-test via a fixture for surrogate reproducibility. Production runtime never sets a seed.

### Claude's Discretion
- Exact directory layout under `backend/app/services/redaction/` vs. a single `redaction_service.py` file (planner picks based on line-count growth — likely a sub-package once `gender_id.py`, `honorifics.py`, `uuid_filter.py` are added).
- Internal data classes for detected entities (likely Pydantic `Entity` model with `type`, `start`, `end`, `score`, `text`).
- Logging format/levels for non-traced operations (DEBUG vs INFO).
- Exact Indonesian honorific list (start with `Pak`, `Bapak`, `Bu`, `Ibu`, `Sdr.`, `Sdri.`; Phase 4-6 can extend).
- Initial Indonesian gender lookup table contents.
- Whether `RedactionResult.entity_map` keys are real values (Phase 1 in-memory only — never logged or persisted in this phase) or surrogate values. Lean toward `real → surrogate` to match what Phase 2's persisted registry will hold.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source PRD (authoritative for v1.0 milestone)
- `docs/PRD-PII-Redaction-System-v1.1.md` §3.1 (Core Principle), §3.6 (Auxiliary LLM Calls), §4.FR-1 (Detection), §4.FR-2 (Anonymization), §4.FR-3.5 (hard-redact registry exclusion), §5.NFR-1 (Performance), §5.NFR-4 (Observability), §6 (Configuration Reference), §7.4 (Two-pass detection rationale), §8 (Dependencies)

### Project + Milestone Plan
- `.planning/PROJECT.md` "Current Milestone" + "Key Decisions" — v1.0 scope and architectural decisions adopted from PRD
- `.planning/REQUIREMENTS.md` "v1 Requirements" — PII-01..05, ANON-01..06, PERF-01, OBS-01 are this phase's REQ-IDs
- `.planning/ROADMAP.md` "Phase 1: Detection & Anonymization Foundation" — goal, dependencies, success criteria

### Codebase Map (existing patterns to follow / reuse)
- `.planning/codebase/CONVENTIONS.md` §"Code Style", §"Logging", §"FastAPI Dependency Patterns", §"LLM / Structured Output Pattern" — service-module shape, traceable decorator, Pydantic models, audit conventions
- `.planning/codebase/STRUCTURE.md` §"Where to Add New Code" → "New backend service" — directory and file conventions

### Concrete code to read before editing (Phase 1 will modify or wrap these)
- `backend/app/main.py` — FastAPI bootstrap; `lifespan` extends with `get_redaction_service()` warm-up call
- `backend/app/config.py` — `Settings(BaseSettings)` class; Phase 1 adds `pii_*`, `tracing_provider`, and Indonesian-redaction-specific env vars
- `backend/app/services/langsmith_service.py` — to be renamed/refactored into `tracing_service.py` with the `@traced` shim and provider switch
- `backend/app/routers/chat.py` and other `@traceable(name=...)` call sites — receive an import-only migration to `@traced` in the same Phase 1 commit
- `backend/requirements.txt` — Phase 1 adds: `presidio-analyzer`, `presidio-anonymizer`, `spacy`, `faker`, `gender-guesser`, `nameparser`, `rapidfuzz`, `langfuse`

### External docs (planner will fetch via context7 / web)
- Microsoft Presidio analyzer + anonymizer docs (custom NLP engine config for `xx_ent_wiki_sm`)
- spaCy multilingual `xx_ent_wiki_sm` model card
- Faker `id_ID` locale documentation
- Langfuse Python SDK `@observe` decorator docs (for the `@traced` shim langfuse path)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`get_settings()` (`backend/app/config.py`)**: Already `@lru_cache`'d Pydantic `BaseSettings`. Phase 1 just appends new fields (`pii_surrogate_entities: str = "PERSON,EMAIL_ADDRESS,..."`, `pii_redact_entities: str = "..."`, `pii_surrogate_score_threshold: float = 0.7`, `pii_redact_score_threshold: float = 0.3`, `tracing_provider: str = ""`, etc.). No new infrastructure needed.
- **`@traceable(name=...)` decorator pattern**: Already established across `document_tool_service.py`, `chat.py`. Phase 1 introduces `@traced(...)` as a strict superset (langsmith provider mode is functionally identical).
- **Lifespan `try/except` pattern (`backend/app/main.py`)**: Existing wrapping for `configure_langsmith()` and stalled-doc recovery — same pattern wraps `get_redaction_service()` warm-up so init failures don't block startup.
- **`logger = logging.getLogger(__name__)` per service**: Phase 1 follows. Use `%s`-style formatting; never include real PII in log messages.
- **`pydantic.BaseModel` for service I/O**: `RedactionResult` follows the established pattern (e.g., `GeneratedDocument`, `ComparisonResult` in `document_tool_service.py`).

### Established Patterns
- **Service module layout**: `backend/app/services/<name>_service.py` (or `<name>/__init__.py` for sub-packages). Module-level singletons at top, public `snake_case` functions, private `_underscore_prefix` helpers.
- **Settings access**: Always via `get_settings()` — never re-instantiated. Phase 1 redaction service accepts no `Settings` argument; reads at module load.
- **`@lru_cache` getters for expensive singletons**: Pattern used by `get_settings()`. Phase 1 uses for Presidio engine, gender detector, nickname dict, Faker instance.
- **No backend formatter (ruff/black)**: Phase 1 follows existing informal style (4-space indent, double quotes, type hints on every function, modern `str | None` union syntax).
- **Environment loading from `.env`**: `SettingsConfigDict(env_file=".env", extra="ignore")` already configured. Phase 1's new env vars Just Work locally.

### Integration Points
- **`backend/app/main.py` `lifespan`**: Add `get_redaction_service()` call after `configure_langsmith()` (or its successor `configure_tracing()`).
- **`backend/app/services/langsmith_service.py`**: Renamed to `tracing_service.py`. `configure_langsmith()` → `configure_tracing()`. `@traceable` import sites across the codebase migrate to `@traced` from the same module — single sed-style search/replace, but verified test pass after.
- **`backend/requirements.txt`**: Append redaction deps. Note Railway image-build time will increase (Presidio + spaCy model download adds ~30-60s).
- **`backend/tests/api/`**: New `test_redaction.py` follows existing pytest convention. Test runs ENV: hits the live spaCy model — initial test run is slow, subsequent runs cached.

</code_context>

<specifics>
## Specific Ideas

- "Pak Bambang" → "Pak Joko Wijaya" in surrogates (preserve Indonesian register, not "Mr. Marcus Smith"). Drives the strip-and-reattach honorific decision (D-02) and the `id_ID` Faker locale (D-04).
- Indonesian-default product → Indonesian Faker even for foreign-named entities. Cultural consistency outweighs locale-detection complexity.
- The PRD §7.5 surname-collision-corruption example ("Aaron Thompson DDS" surrogate corrupting real "Margaret Thompson") is the test case D-07 (strict surname x-check) is designed to prevent — keep this scenario in the Phase 1 test suite.
- Tracing must work offline (developer can skip provider entirely with `TRACING_PROVIDER=""` and the `@traced` decorator becomes a no-op). Don't make local dev painful.

</specifics>

<deferred>
## Deferred Ideas

- **Conversation-scoped registry persistence** — Phase 2 (REG-01..05). Phase 1 ships in-memory per-call only.
- **Registry round-trip de-anonymization** — Phase 2 (DEANON-01..02) and Phase 4 (DEANON-03..05).
- **Entity resolution / nickname clustering** — Phase 3 (RESOLVE-01..04).
- **`LLM_PROVIDER` switch + pre-flight egress filter** — Phase 3 (PROVIDER-01..07).
- **Chat-loop integration (SSE buffering, `redaction_status` events)** — Phase 5 (BUFFER-01..03, TOOL-01..04).
- **Per-entity-type thresholds** (PERSON=0.6, EMAIL=0.5 …) — Phase 6 hardening if eval data justifies.
- **Numbered hard-redact placeholders** (`[CREDIT_CARD_1]`, `[CREDIT_CARD_2]`) — revisit only if user feedback demands disambiguation.
- **Admin-only `POST /admin/redaction/test` endpoint** — Phase 5 (will be subsumed by chat integration); skip in Phase 1.
- **Surname-rejection logging** for Faker tuning — Phase 6 observability hardening.
- **Bahasa-Indonesia academic title handling** (`S.H.`, `M.H.`, `Dr.`, `Prof.`) — Phase 4 prompt-guidance phase, where reformatting concerns are addressed.
- **Faker locale auto-detect** based on per-entity language — speculative; never raised as a real user need.
- **`langdetect` integration for entity-language routing** — same as above.
- **Code-switched ID/EN legal text handling** — open question, no user evidence yet; defer until eval shows it's a problem.

</deferred>

---

*Phase: 01-detection-anonymization-foundation*
*Context gathered: 2026-04-25*
