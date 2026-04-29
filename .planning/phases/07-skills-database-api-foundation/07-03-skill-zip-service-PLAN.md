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

Pure stdlib service module that **builds** a SKILL.md-format ZIP (frontmatter + instructions body + scripts/references/assets) for export, and **parses** an uploaded ZIP into a structured `ParsedSkill` list for import. No network, no DB, no FastAPI — all router-side glue lives in 07-04. Unit-tested in isolation so the convergence loop on the router doesn't drag ZIP correctness into integration.

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

class ParsedSkill(BaseModel):
    frontmatter: SkillFrontmatter
    instructions_md: str        # body after frontmatter
    files: list[ParsedSkillFile]
    error: str | None = None    # populated by parser if invalid; never raised

class SkillImportItem(BaseModel):
    name: str
    status: Literal["created", "error", "skipped"]
    skill_id: str | None = None
    error: str | None = None

class ImportResult(BaseModel):
    created_count: int
    error_count: int
    results: list[SkillImportItem]
```

## Public functions

### `build_skill_zip(skill: dict, files: list[dict], file_bytes_loader: Callable[[str], bytes]) -> BytesIO`

- Composes `SKILL.md` = `yaml.safe_dump(frontmatter)` + `"---\n"` + instructions body.
- Writes each file at its `relative_path` using `zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)`.
- `file_bytes_loader(storage_path)` is injected so the router can wire it to `storage.from_('skills-files').download(...)`; the service stays pure.
- Returns the in-memory `BytesIO` with `seek(0)` already applied — caller wraps in `StreamingResponse`.

### `parse_skill_zip(zip_bytes: bytes, *, max_per_file: int = 10*1024*1024, max_total: int = 50*1024*1024) -> list[ParsedSkill]`

- **Layout detection**: bulk (multiple top-level dirs each containing `SKILL.md`) vs single (`SKILL.md` at root) vs single-named-dir (`my-skill/SKILL.md`).
- **Per-skill walk**: parse YAML frontmatter via `yaml.safe_load` (NEVER `yaml.load` — security). Strip frontmatter from body for `instructions_md`.
- **File routing**: only files prefixed `scripts/`, `references/`, or `assets/` are kept; anything else (including dotfiles) is silently dropped. `SKILL.md` itself is consumed, not added to `files`.
- **Per-file size violations**: file omitted from `files` and an `error` note appended to that ParsedSkill — does NOT raise. (Router decides whether to surface per-file as `skipped` or `error`.)
- **Total size violation**: > `max_total` → raises `ValueError("ZIP exceeds 50 MB limit")` (router catches → 413). The check uses the **uncompressed sum** of `ZipInfo.file_size` (ZIP-bomb defense) before reading any content.
- **Path traversal defense**: reject any entry whose `relative_path` contains `..` or starts with `/`; entries failing the check are dropped with an error note.
- **Name validation**: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`, ≤ 64 chars. Invalid → `ParsedSkill.error` set, not raised.
- **Unicode filenames**: rejected (ASCII-only) for the SKILL name; file contents are unrestricted; file relative_paths must be ASCII to avoid storage-path collisions across OSes.

## Test coverage (`test_skill_zip_service.py`)

1. **Round-trip**: `build_skill_zip` → `parse_skill_zip` → equal frontmatter, equal file count, equal body, byte-equal file contents.
2. **Single-skill layouts**: SKILL.md at root; SKILL.md in named subdir.
3. **Bulk ZIP**: 3 skills — one valid, one with bad name, one with missing required frontmatter field. Expect 3 results with correct `error` values.
4. **Per-file size**: 11 MB file dropped (with error note); 9 MB file kept.
5. **Total size**: 51 MB ZIP (uncompressed sum) raises `ValueError`.
6. **Frontmatter edge cases**: missing `name`, missing `description`, malformed YAML, non-ASCII name — each yields a `ParsedSkill` with `error` populated.
7. **Path traversal**: ZIP with `../escape.md` entry — entry dropped, error noted; no file written.
8. **Layout disambiguation**: SKILL.md alone at root + a stray top-level `README.md` is interpreted as single-skill, not bulk.

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
