# Phase 8: LLM Tool Integration & Discovery - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-30
**Phase:** 8-LLM Tool Integration & Discovery
**Areas discussed:** Catalog injection, save_skill on conflict, read_skill_file limits, Skill catalog format

---

## Catalog Injection

### Q1: How should the skill catalog be integrated into the system prompt?

| Option | Description | Selected |
|--------|-------------|----------|
| Append block | Keep SYSTEM_PROMPT static; fetch skills async, append as block — same pattern as pii_guidance | ✓ |
| build_system_prompt() helper | Replace static constant with async function assembling all parts | |
| Separate system message | Inject as a second system message | |

**User's choice:** Append block pattern — `SYSTEM_PROMPT + pii_guidance + skill_catalog_block`
**Notes:** Minimal refactor, consistent with the pii_guidance precedent in chat.py.

### Q2: Empty catalog behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Skip the block entirely | Return "" when 0 enabled skills — nothing appended | ✓ |
| Show empty placeholder | Append "No skills currently enabled" note | |

**User's choice:** Skip block entirely — no empty section, saves tokens.

### Q3: Multi-agent path injection

| Option | Description | Selected |
|--------|-------------|----------|
| Both paths | Inject on single-agent AND multi-agent (agent_def.system_prompt) paths | ✓ |
| Single-agent only | Only inject in the main agent path | |

**User's choice:** Both paths — skills should work regardless of which agent is active.

### Q4: Skill tool registration

| Option | Description | Selected |
|--------|-------------|----------|
| Always registered | load_skill/save_skill/read_skill_file unconditionally in tool list | ✓ |
| Conditionally registered | Only add tools when user has ≥1 enabled skill (adds DB round-trip) | |

**User's choice:** Always registered — simpler, consistent with web_search pattern.

---

## save_skill on Conflict

### Q1: Name collision behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Error — LLM resolves | Return error with existing_skill_id + hint for LLM to rename or update | ✓ |
| Upsert by name | Silently update existing skill with same name | |
| Always create new | Always insert new row (conflicts with UNIQUE constraint) | |

**User's choice:** Error with existing_skill_id hint — prevents silent overwrites, gives LLM the ID to use.

### Q2: Update scope with update=true

| Option | Description | Selected |
|--------|-------------|----------|
| Any owned skill | update=true + skill_id can update any skill owned by user | ✓ |
| Current-session only | Only skills created in this conversation can be updated | |

**User's choice:** Any owned skill — standard ownership check (same as PATCH /skills/{id}).

### Q3: Success response

| Option | Description | Selected |
|--------|-------------|----------|
| Full skill object | Return {skill_id, name, description, instructions, enabled, message} | ✓ |
| Minimal — ID + name | Return just {skill_id, name, message} | |

**User's choice:** Full skill object — LLM can confirm what was persisted.

---

## read_skill_file Limits

### Q1: Large text file handling

| Option | Description | Selected |
|--------|-------------|----------|
| Truncate at 8,000 chars | Cap inline content, include truncated flag and total_bytes | ✓ |
| Return full content | No cap — risks overwhelming context window for large files | |
| Configurable limit | Admin sets limit via system_settings | |

**User's choice:** Truncate at 8,000 chars with truncated notice — consistent with search_documents chunk sizing.

### Q2: Binary file handling

| Option | Description | Selected |
|--------|-------------|----------|
| Metadata + explanation | Return filename/mime/size, readable=false, no URL | ✓ |
| Signed download URL | Return short-lived URL for manual download | |

**User's choice:** Metadata only — the LLM can't follow URLs; binary files are for sandbox/human use.

### Q3: Text vs binary classification

| Option | Description | Selected |
|--------|-------------|----------|
| MIME type from DB | mime_type.startswith("text/") → readable; else binary | ✓ |
| Content sniffing | Download bytes to detect binary — adds latency | |

**User's choice:** MIME type from DB — fast, no extra I/O, consistent with Phase 7 storage.

---

## Skill Catalog Format

### Q1: Catalog format

| Option | Description | Selected |
|--------|-------------|----------|
| Markdown table | \| Skill \| Description \| with anti-speculation guardrail header | ✓ |
| Numbered list | 1. name — description | |
| Name-only | Just names, no descriptions | |

**User's choice:** Markdown table — structured, scannable, best for LLM recognition.

### Q2: Skills cap

| Option | Description | Selected |
|--------|-------------|----------|
| Cap at 20 skills | First 20 by name, ~1,000 token max overhead | ✓ |
| No cap | All enabled skills — unbounded token usage | |
| Cap at 10 skills | More conservative | |

**User's choice:** Cap at 20 skills ordered alphabetically.

### Q3: Footer on cap hit

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — add footer | "Showing 20 of N skills. Call load_skill with any skill name..." | ✓ |
| No — silently cap | Just show 20, no overflow indicator | |

**User's choice:** Footer note — LLM knows there are more skills beyond the visible catalog.

---

## Claude's Discretion

- `build_skill_catalog_block` lives in a new `backend/app/services/skill_catalog_service.py`
- `load_skill` response includes files table to fulfill SFILE-02
- `read_skill_file` input uses `filename` (flat name) rather than UUID for natural LLM referencing
- New file endpoints follow `multipart/form-data` pattern from `/documents/upload`

## Deferred Ideas

- Skills tab in navigation — Phase 9
- Skill editor UI — Phase 9
- File preview panel — Phase 9 (SFILE-04)
- Code execution sandbox — Phase 10
- Admin-configurable catalog cap — deferred until users hit the 20-skill limit in practice
- Skill ranking beyond alphabetical — future phase if needed
