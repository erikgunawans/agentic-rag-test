---
id: 07-03
phase: 7
title: skill_zip_service — ZIP export/import utility (build + parse)
wave: 1
depends_on: []
closes: [EXPORT-01-logic, EXPORT-02-parser]
estimated_atomic_commits: 2
---

# 07-03-PLAN — `skill_zip_service.py` (ZIP export/import utility)

## Goal

Service module (Python stdlib + PyYAML) that **builds** a SKILL.md-format ZIP (frontmatter + instructions body + scripts/references/assets) for export, and **parses** an uploaded ZIP into a structured `ParsedSkill` list for import. No network, no DB, no FastAPI — all router-side glue lives in 07-04. Unit-tested in isolation so the convergence loop on the router doesn't drag ZIP correctness into integration. (Cycle-1 review LOW: clarified that PyYAML is the one external dependency.)

## Closes

- **EXPORT-01** (the build/serialization logic — router-side streaming response is in 07-04).
- **EXPORT-02** (the import parser logic — router-side multipart handling is in 07-04).

## Files to create / modify

- `backend/app/services/skill_zip_service.py` (new)
- `backend/tests/api/test_skill_zip_service.py` (new — pure unit tests, no `httpx`)
- `backend/requirements.txt` (modified — add `PyYAML>=6.0`; verified absent today)

## Pydantic models (top of module)

```python
class SkillFrontmatter(BaseModel):
    name: str
    description: str
    license: str | None = None
    compatibility: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class ParsedSkillFile(BaseModel):
    relative_path: str          # "scripts/foo.py" | "references/x.md" | "assets/y.png"
    content: bytes
    size_bytes: int

class SkippedFile(BaseModel):
    """Cycle-1 review HIGH #5: oversized/path-traversal/etc. files are reported
    here, NOT via ParsedSkill.error. The skill is still created; only the file
    is skipped. This matches D-P7-08 (oversized file skipped, skill kept).
    """
    relative_path: str
    reason: Literal["oversized", "path_traversal", "outside_layout", "non_ascii_path"]
    size_bytes: int | None = None

class ParsedSkill(BaseModel):
    """Cycle-2 review NEW-H2 fix: success fields are Optional/defaulted so the parser
    can construct a ParsedSkill with ONLY `error` set when SKILL.md is unparseable
    (missing frontmatter delimiter, malformed YAML, missing required fields, bad name).
    Consumers MUST check `if skill.error: ... else: ...` first; once error is None,
    `frontmatter` is guaranteed non-None and `instructions_md` is guaranteed non-empty.
    """
    frontmatter: SkillFrontmatter | None = None
    instructions_md: str = ""        # body after frontmatter (empty when error set)
    files: list[ParsedSkillFile] = Field(default_factory=list)
    skipped_files: list[SkippedFile] = Field(default_factory=list)  # soft per-file warnings
    error: str | None = None    # ONLY for fatal skill-level errors (bad name, malformed YAML, missing required frontmatter); NEVER for per-file issues

class SkillImportItem(BaseModel):
    name: str
    status: Literal["created", "error", "skipped"]
    skill_id: str | None = None
    error: str | None = None
    skipped_files: list[SkippedFile] = Field(default_factory=list)  # surfaced to API caller so the UI can warn about partially-imported skills

class ImportResult(BaseModel):
    created_count: int
    error_count: int
    results: list[SkillImportItem]
```

## Public functions

### `build_skill_zip(skill: dict, files: list[dict], file_bytes_loader: Callable[[str], bytes]) -> BytesIO`

- Composes `SKILL.md` = `"---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n" + instructions_body`. **Cycle-1 review HIGH #4 fix**: the leading `---\n` delimiter MUST be present — without it the file is not a valid agentskills.io frontmatter document and EXPORT-01 round-trip fails.
- Writes each file at its `relative_path` using `zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)`.
- `file_bytes_loader(storage_path)` is injected so the router can wire it to `storage.from_('skills-files').download(...)`; the service stays pure.
- Returns the in-memory `BytesIO` with `seek(0)` already applied — caller wraps in `StreamingResponse`.

### `parse_skill_zip(zip_bytes: bytes, *, max_per_file: int = 10*1024*1024, max_total: int = 50*1024*1024) -> list[ParsedSkill]`

- **Frontmatter parsing**: SKILL.md MUST start with a `---` delimiter line; if absent, treat as missing-frontmatter → `ParsedSkill.error = "SKILL.md has no frontmatter delimiter"`. Parse YAML via `yaml.safe_load` (NEVER `yaml.load` — security). Strip frontmatter (everything between the two `---` lines) from body for `instructions_md`.
- **Layout detection**: bulk (multiple top-level dirs each containing `SKILL.md`) vs single (`SKILL.md` at root) vs single-named-dir (`my-skill/SKILL.md`).
- **Per-skill walk**: walk file entries under each skill's root.
- **File routing**: only files prefixed `scripts/`, `references/`, or `assets/` are kept; anything else (including dotfiles) is recorded in `skipped_files` with `reason="outside_layout"` (the skill itself is still created — they're soft warnings, not errors). `SKILL.md` itself is consumed, not added to `files`.
- **Per-file size violations** (cycle-1 review HIGH #5 fix): file is omitted from `files` and added to `skipped_files` with `reason="oversized"`. The skill is **still created** (matches D-P7-08). The router (07-04) reads `skipped_files` and surfaces it on the SkillImportItem, but does NOT mark the skill as `error`.
- **Total size violation**: > `max_total` → raises `ValueError("ZIP exceeds 50 MB limit")` (router catches → 413). The check uses the **uncompressed sum** of `ZipInfo.file_size` (ZIP-bomb defense) before reading any content.
- **Path traversal defense**: reject any entry whose `relative_path` contains `..`, starts with `/`, or normalizes outside the skill root (`pathlib.PurePosixPath.is_relative_to`). Entries failing the check go to `skipped_files` with `reason="path_traversal"`.
- **Name validation**: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`, ≤ 64 chars. Invalid → `ParsedSkill.error` set, not raised. **Skill-level fatal**: ParsedSkill created with no `files`; router treats as `error`.
- **Required frontmatter fields**: `name`, `description` MUST be present. Missing → `ParsedSkill.error = "Missing required frontmatter field: <field>"`. Malformed YAML → `ParsedSkill.error = "Malformed YAML frontmatter: <yaml.YAMLError msg>"`.
- **Unicode in skill name**: rejected (ASCII-only) → `ParsedSkill.error`. **Unicode in file relative_path**: file goes to `skipped_files` with `reason="non_ascii_path"`; skill still created.

## Test coverage (`test_skill_zip_service.py`)

1. **Round-trip**: `build_skill_zip` → `parse_skill_zip` → equal frontmatter, equal file count, equal body, byte-equal file contents. Asserts the produced SKILL.md starts with `---\n`.
2. **Single-skill layouts**: SKILL.md at root; SKILL.md in named subdir.
3. **Bulk ZIP**: 3 skills — one valid, one with bad name, one with missing required frontmatter field. Expect 3 results with correct skill-level `error` values; `skipped_files` empty for all three.
4. **Per-file size (HIGH #5 regression)**: ZIP has one 11 MB file in `assets/big.bin` and one 9 MB file in `references/ok.md`. Expect `ParsedSkill.error is None`, `len(files) == 1` (only ok.md), `len(skipped_files) == 1` with `reason="oversized"` and `relative_path="assets/big.bin"`.
5. **Total size**: 51 MB ZIP (uncompressed sum) raises `ValueError("ZIP exceeds 50 MB limit")`.
6. **Frontmatter edge cases**: missing `name`, missing `description`, malformed YAML, non-ASCII skill name — each yields a `ParsedSkill` with `error` populated; `skipped_files` empty.
7. **Frontmatter delimiter (HIGH #4 regression)**: SKILL.md without a leading `---` line → `ParsedSkill.error = "SKILL.md has no frontmatter delimiter"`.
8. **Path traversal**: ZIP with `../escape.md` entry — entry goes to `skipped_files` with `reason="path_traversal"`, skill still created with the rest of its files.
9. **Layout disambiguation**: SKILL.md alone at root + a stray top-level `README.md` is interpreted as single-skill, not bulk; the README is a `skipped_files` entry with `reason="outside_layout"`.
10. **Outside layout**: file at `notes/private.md` (not under `scripts|references|assets`) → `skipped_files` with `reason="outside_layout"`.
11. **Round-trip preserves the leading `---`**: build → parse the resulting bytes → reparse the inner SKILL.md text and assert it begins with `---\n`.

## Reuses

- Python stdlib `zipfile`, `io.BytesIO`, `pathlib.PurePosixPath`.
- `yaml.safe_load` / `yaml.safe_dump` from PyYAML (added by this plan to `requirements.txt`).
- Pydantic v2 (already in `requirements.txt`).

## Verification

- `cd backend && source venv/bin/activate && pip install -r requirements.txt` succeeds (PyYAML resolves).
- `python -c "from app.services.skill_zip_service import build_skill_zip, parse_skill_zip; print('OK')"` prints OK.
- `pytest tests/api/test_skill_zip_service.py -v` — all cases pass.

## Atomic commits (two)

1. `chore(deps): add PyYAML for skill ZIP frontmatter parsing`
2. `feat(skills): skill_zip_service for ZIP export/import (EXPORT-01/02 logic)`

The dependency commit lands first so any reviewer running `pip install` between commits doesn't see an `ImportError`.

## Risks / open verifications

- **PyYAML on Python 3.14**: project uses 3.14 (PROGRESS.md). PyYAML 6.0+ supports 3.14; pin loosely (`>=6.0,<7`) to allow upgrades.
- **Streaming for large exports**: `BytesIO` materializes the whole ZIP in memory. Within Phase 7 limits (50 MB total) this is acceptable (~< 0.5s on the Railway 8 GB plan). Phase 8+ may revisit if export latency becomes a concern.
- **ZIP bomb**: defended via `max_total` check on uncompressed sum BEFORE reading content; reviewers should still confirm no `ZipFile.read()` happens for entries that would push over the budget.
