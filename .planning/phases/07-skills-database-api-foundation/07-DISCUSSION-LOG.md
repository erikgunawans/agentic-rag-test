# Phase 7: Skills Database & API Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-29
**Phase:** 07-skills-database-api-foundation
**Areas discussed:** Share/unshare ownership, ZIP import file scope, Seed skill-creator content, Bulk import response schema

---

## Share/Unshare Ownership

| Option | Description | Selected |
|--------|-------------|----------|
| user_id + created_by | user_id becomes NULL when global; created_by is immutable provenance for unsharing and storage paths | ✓ |
| user_id + is_global flag | user_id always stays as creator, is_global flag controls visibility. Matches existing is_global pattern. | |
| user_id=NULL, no unshare | Once global, permanently global. Simpler schema but SKILL-06 allows toggle back. | |

**User's choice:** user_id + created_by (Recommended)
**Notes:** Enables full toggle-back behaviour while keeping the PRD's user_id=NULL success criterion for global skill visibility.

---

### Who can share?

| Option | Description | Selected |
|--------|-------------|----------|
| Any user (owner) | Anyone can share their own skill with all users. Matches SKILL-06. | ✓ |
| Admin only | Only super_admin can publish global skills. More quality control. | |

**User's choice:** Any user (owner of that skill)

---

### Editing global skills

| Option | Description | Selected |
|--------|-------------|----------|
| Blocked — unshare first | PATCH returns 403 if user_id IS NULL. Creator must unshare first. Global skills stay immutable. | ✓ |
| Creator can always edit | created_by grants edit even when global. Live edits visible to all users. | |

**User's choice:** Blocked — unshare first (Recommended)

---

### Admin moderation

| Option | Description | Selected |
|--------|-------------|----------|
| Admin can delete any global skill | super_admin can DELETE regardless of created_by. Moderation escape hatch. | ✓ |
| Creator only | Only created_by can delete. No moderation path for admins. | |

**User's choice:** Admin can delete any global skill (Recommended)

---

## ZIP Import File Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Store them (full import) | Phase 7 creates skill_files table + skills-files bucket. Files from ZIP subdirs stored now. | ✓ |
| Skip files, metadata only | Only SKILL.md extracted. File subdirs dropped. Phase 8 handles file storage. | |

**User's choice:** Store them (full import) (Recommended)
**Notes:** Ensures imported ZIPs don't lose attached resources. Phase 8 adds the UI layer on top of the data foundation.

---

### Storage path

| Option | Description | Selected |
|--------|-------------|----------|
| skills-files bucket, {user_id}/{skill_id}/{filename} | Private bucket, path matches PRD. | ✓ |
| Existing storage_bucket, skills/{skill_id}/{filename} | Reuse document bucket. Mixes concerns. | |

**User's choice:** skills-files bucket, path: {user_id}/{skill_id}/{filename} (Recommended)

---

### Per-file size limit

| Option | Description | Selected |
|--------|-------------|----------|
| 10 MB per file | Reasonable individual cap within 50MB ZIP total. | ✓ |
| No per-file limit (50MB total only) | Simpler, but one large file can consume entire quota. | |

**User's choice:** 10 MB per file (Recommended)

---

## Seed Skill-Creator Content

| Option | Description | Selected |
|--------|-------------|----------|
| LexCore-tailored guide | Legal-domain examples, naming/description best practices, save_skill call guidance bespoke to LexCore. | ✓ |
| Generic agent skills guide | Platform-neutral skill creation guide. More portable but less relevant to LexCore users. | |

**User's choice:** LexCore-tailored guide (Recommended)

---

### save_skill guidance

| Option | Description | Selected |
|--------|-------------|----------|
| Include save_skill call guidance | Instructions tell AI to call save_skill after collaborating. Phase 8 wires the tool. | ✓ |
| Keep instructions human-readable only | No tool mentions. Phase 8 adds tool-call behavior separately. | |

**User's choice:** Yes — include save_skill call guidance (Recommended)

---

### Seeding mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| SQL INSERT in migration 034 | Consistent with migration pattern. Auto-applied on fresh setup. | ✓ |
| Python seed script | More flexible but extra script to manage. | |

**User's choice:** SQL INSERT in migration 034 (Recommended)

---

## Bulk Import Response Schema

| Option | Description | Selected |
|--------|-------------|----------|
| Array of per-skill results | {results: [{name, status, skill_id?, error?}], created_count, error_count}. Clear per-skill breakdown. | ✓ |
| Simple counts + error list | {created: N, errors: [...]}. Less structured, harder to map errors to skills in UI. | |

**User's choice:** Array of per-skill results (Recommended)

---

### Naming conflict handling

| Option | Description | Selected |
|--------|-------------|----------|
| Error + skip | Report conflict error, continue with other skills. User renames and re-imports. | ✓ |
| Auto-suffix rename | Append -2, -3 etc. Unexpected renames may confuse. | |

**User's choice:** Error + skip (Recommended)

---

### Import content type

| Option | Description | Selected |
|--------|-------------|----------|
| multipart/form-data | Consistent with /documents/upload. apiFetch already handles FormData. | ✓ |
| JSON with base64-encoded ZIP | Simpler for programmatic clients but breaks existing apiFetch pattern. | |

**User's choice:** multipart/form-data (Recommended)

---

## Claude's Discretion

- Migration split: 034 for skills table + seed, 035 for skill_files table + bucket policy
- Name validation regex: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`
- `skill_zip_service.py` uses Python stdlib `zipfile` (no new dependencies)
- Storage path for global skills: use `created_by` as owner prefix (user_id is NULL); for system seeds use `_system/{skill_id}/{filename}`
- Index strategy: `(user_id, name)` for conflict checks; partial on `(name) WHERE user_id IS NULL` for global lookups

## Deferred Ideas

- `GET /skills/{id}/files/{file_id}/content` endpoint — deferred to Phase 8 (with LLM tool wiring)
- Skill analytics / versioning — deferred per REQUIREMENTS.md §Future Requirements
- Skill catalog injection into system prompt — Phase 8
