"""
skill_zip_service.py — ZIP export/import utility for the Skills Open Standard.

Builds SKILL.md-format ZIPs (frontmatter + instructions body + scripts/references/assets)
for export, and parses uploaded ZIPs into ParsedSkill structures for import.

No network, no DB, no FastAPI — all router-side glue lives in 07-04.
Uses Python stdlib (zipfile, io.BytesIO, pathlib.PurePosixPath) + PyYAML.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import PurePosixPath
from typing import Any, Callable, Literal

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

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
    """
    Oversized, path-traversal, outside-layout, or non-ASCII-path files are
    reported here — NOT via ParsedSkill.error.  The skill is still created;
    only the file is skipped.  Matches D-P7-08.
    """
    relative_path: str
    reason: Literal["oversized", "path_traversal", "outside_layout", "non_ascii_path"]
    size_bytes: int | None = None


class ParsedSkill(BaseModel):
    """
    On a fatal skill-level error (bad name, malformed YAML, missing required fields,
    missing frontmatter delimiter) only `error` is set and all other fields hold their
    defaults.  Consumers MUST check `if skill.error: ... else: ...` first.

    Once error is None, `frontmatter` is guaranteed non-None and `instructions_md`
    is guaranteed non-empty (or at least a valid empty string from the body).
    """
    frontmatter: SkillFrontmatter | None = None
    instructions_md: str = ""        # body after frontmatter (empty when error set)
    files: list[ParsedSkillFile] = Field(default_factory=list)
    skipped_files: list[SkippedFile] = Field(default_factory=list)
    error: str | None = None    # ONLY for fatal skill-level errors; NEVER for per-file issues


class SkillImportItem(BaseModel):
    name: str
    status: Literal["created", "error", "skipped"]
    skill_id: str | None = None
    error: str | None = None
    skipped_files: list[SkippedFile] = Field(default_factory=list)


class ImportResult(BaseModel):
    created_count: int
    error_count: int
    results: list[SkillImportItem]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SKILL_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_SKILL_NAME_MAX = 64
_ALLOWED_FILE_PREFIXES = ("scripts/", "references/", "assets/")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compose_skill_md(frontmatter_dict: dict[str, Any], instructions_body: str) -> str:
    """
    Compose a SKILL.md file string.
    Leading '---' delimiter MUST be present for valid agentskills.io format (HIGH #4).
    """
    yaml_str = yaml.safe_dump(frontmatter_dict, sort_keys=False, allow_unicode=True)
    return f"---\n{yaml_str}---\n{instructions_body}"


def _parse_skill_md(skill_md_text: str) -> ParsedSkill:
    """
    Parse a SKILL.md text into a ParsedSkill (with error set on any fatal condition).
    Returns a ParsedSkill with error=None and frontmatter set on success.
    """
    # MUST start with a '---' delimiter line
    if not skill_md_text.startswith("---"):
        return ParsedSkill(error="SKILL.md has no frontmatter delimiter")

    # Find the closing '---' delimiter
    rest = skill_md_text[3:]            # skip opening ---
    # Allow optional \r after ---
    if rest.startswith("\r\n"):
        rest = rest[2:]
    elif rest.startswith("\n"):
        rest = rest[1:]
    else:
        return ParsedSkill(error="SKILL.md has no frontmatter delimiter")

    # Find the closing ---
    delim_idx = rest.find("\n---")
    if delim_idx == -1:
        return ParsedSkill(error="SKILL.md has no frontmatter delimiter")

    yaml_block = rest[:delim_idx]
    after_delim = rest[delim_idx + 4:]  # skip \n---
    if after_delim.startswith("\r\n"):
        instructions_md = after_delim[2:]
    elif after_delim.startswith("\n"):
        instructions_md = after_delim[1:]
    else:
        instructions_md = after_delim

    # Parse YAML
    try:
        data = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        return ParsedSkill(error=f"Malformed YAML frontmatter: {exc}")

    if not isinstance(data, dict):
        return ParsedSkill(error="Malformed YAML frontmatter: expected mapping")

    # Required fields
    for field in ("name", "description"):
        if field not in data:
            return ParsedSkill(error=f"Missing required frontmatter field: {field}")

    name: str = data["name"]

    # Validate name: ASCII-only first
    try:
        name.encode("ascii")
    except UnicodeEncodeError:
        return ParsedSkill(error=f"Skill name must be ASCII: {name!r}")

    # Validate name pattern
    if not _SKILL_NAME_RE.match(name) or len(name) > _SKILL_NAME_MAX:
        return ParsedSkill(
            error=f"Invalid skill name {name!r}: must match ^[a-z][a-z0-9]*(-[a-z0-9]+)*$ and be <= 64 chars"
        )

    fm = SkillFrontmatter(
        name=name,
        description=data.get("description", ""),
        license=data.get("license"),
        compatibility=data.get("compatibility"),
        metadata={k: v for k, v in data.items() if k not in {"name", "description", "license", "compatibility"}},
    )
    return ParsedSkill(frontmatter=fm, instructions_md=instructions_md)


def _is_path_safe(rel_path: str, skill_root: str) -> bool:
    """
    Return True if rel_path is safe (no traversal outside skill_root).
    rel_path is relative to skill_root within the ZIP.
    """
    try:
        p = PurePosixPath(rel_path)
    except Exception:
        return False
    # Must not start with /
    if p.is_absolute():
        return False
    # Must not contain ..
    parts = p.parts
    if ".." in parts:
        return False
    return True


def _classify_relative(path_within_skill: str) -> Literal["skill_md", "allowed", "outside"]:
    """
    Classify a path relative to the skill root.
    """
    if path_within_skill == "SKILL.md":
        return "skill_md"
    for prefix in _ALLOWED_FILE_PREFIXES:
        if path_within_skill.startswith(prefix):
            return "allowed"
    return "outside"


def _parse_single_skill(
    zf: zipfile.ZipFile,
    entries: list[zipfile.ZipInfo],
    skill_root: str,
    *,
    max_per_file: int,
) -> ParsedSkill:
    """
    Parse one skill from a list of ZIP entries under `skill_root`.

    `skill_root` is either "" (root) or "some-skill-dir/" (with trailing slash).
    Entries are full ZIP paths. skill_root is stripped to get the path within skill.
    """
    skill_md_text: str | None = None
    skipped: list[SkippedFile] = []
    collected: list[ParsedSkillFile] = []

    for info in entries:
        full_name: str = info.filename
        if full_name.endswith("/"):
            continue  # directory entry — skip

        # Strip skill root prefix to get relative path within skill
        if skill_root:
            if full_name.startswith(skill_root):
                rel = full_name[len(skill_root):]
            else:
                continue
        else:
            rel = full_name

        if not rel:
            continue

        # Path traversal check
        if not _is_path_safe(rel, skill_root):
            skipped.append(SkippedFile(
                relative_path=rel,
                reason="path_traversal",
                size_bytes=info.file_size,
            ))
            continue

        # Non-ASCII path check
        try:
            rel.encode("ascii")
        except UnicodeEncodeError:
            skipped.append(SkippedFile(
                relative_path=rel,
                reason="non_ascii_path",
                size_bytes=info.file_size,
            ))
            continue

        classification = _classify_relative(rel)

        if classification == "skill_md":
            # Read SKILL.md — apply per-file size guard
            if info.file_size > max_per_file:
                # SKILL.md itself is oversized — treat as fatal missing
                return ParsedSkill(error="SKILL.md exceeds per-file size limit")
            raw = zf.read(full_name)
            skill_md_text = raw.decode("utf-8", errors="replace")

        elif classification == "allowed":
            # Per-file size check (HIGH #5)
            if info.file_size > max_per_file:
                skipped.append(SkippedFile(
                    relative_path=rel,
                    reason="oversized",
                    size_bytes=info.file_size,
                ))
                continue
            content = zf.read(full_name)
            collected.append(ParsedSkillFile(
                relative_path=rel,
                content=content,
                size_bytes=len(content),
            ))

        else:
            # outside_layout — soft warning
            skipped.append(SkippedFile(
                relative_path=rel,
                reason="outside_layout",
                size_bytes=info.file_size,
            ))

    if skill_md_text is None:
        return ParsedSkill(error="No SKILL.md found in skill")

    result = _parse_skill_md(skill_md_text)
    if result.error:
        return result

    # Attach files and skipped to the successfully-parsed skill
    result.files = collected
    result.skipped_files = skipped
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_skill_zip(
    skill: dict[str, Any],
    files: list[dict[str, Any]],
    file_bytes_loader: Callable[[str], bytes],
) -> io.BytesIO:
    """
    Build an in-memory ZIP containing SKILL.md and all skill files.

    Args:
        skill:             Dict with at minimum 'name', 'description', plus optional
                           'license', 'compatibility', 'instructions' (body text).
        files:             List of dicts with 'relative_path' (e.g. "scripts/foo.py")
                           and 'storage_path' (path in Supabase Storage).
        file_bytes_loader: Callable that accepts a storage_path and returns raw bytes.
                           Router wires this to supabase storage.download().

    Returns:
        BytesIO positioned at 0 (seek(0) already applied).
    """
    # Build frontmatter dict for YAML serialization
    fm: dict[str, Any] = {
        "name": skill.get("name", ""),
        "description": skill.get("description", ""),
    }
    if skill.get("license"):
        fm["license"] = skill["license"]
    if skill.get("compatibility"):
        fm["compatibility"] = skill["compatibility"]
    # Merge only user-authored metadata JSONB — never expose DB columns (id, user_id, etc.)
    fm.update(skill.get("metadata") or {})

    instructions_body: str = skill.get("instructions", "")
    skill_md_content = _compose_skill_md(fm, instructions_body)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", skill_md_content.encode("utf-8"))
        for file_info in files:
            rel_path: str = file_info["relative_path"]
            storage_path: str = file_info["storage_path"]
            content = file_bytes_loader(storage_path)
            zf.writestr(rel_path, content)

    buf.seek(0)
    return buf


def parse_skill_zip(
    zip_bytes: bytes,
    *,
    max_per_file: int = 10 * 1024 * 1024,     # 10 MB per file
    max_total: int = 50 * 1024 * 1024,         # 50 MB total uncompressed
) -> list[ParsedSkill]:
    """
    Parse an uploaded ZIP into a list of ParsedSkill objects.

    Layout auto-detection:
    - Bulk:        multiple top-level dirs each containing SKILL.md
    - Single-root: SKILL.md at root level
    - Single-named: exactly one top-level dir containing SKILL.md

    Security:
    - ZIP-bomb defense via max_total on uncompressed sum BEFORE reading content.
    - Path traversal: entries with '..' or absolute paths → skipped_files.
    - Per-file size: oversized → skipped_files (skill still created).
    - Total size: > max_total → raises ValueError("ZIP exceeds 50 MB limit").

    Args:
        zip_bytes:    Raw ZIP bytes.
        max_per_file: Per-file uncompressed byte limit (default 10 MB).
        max_total:    Total uncompressed bytes limit (default 50 MB).

    Returns:
        List of ParsedSkill objects (may include error-flagged skills).

    Raises:
        ValueError: If the ZIP exceeds max_total uncompressed size.
        zipfile.BadZipFile: If zip_bytes is not a valid ZIP.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # ZIP-bomb defense: check total uncompressed size before reading any content
        total_uncompressed = sum(info.file_size for info in zf.infolist())
        if total_uncompressed > max_total:
            raise ValueError("ZIP exceeds 50 MB limit")

        all_entries = zf.infolist()

        # -------------------------------------------------------------------
        # Layout detection
        # -------------------------------------------------------------------
        # Collect top-level names (not directories themselves, just the first component)
        top_level_dirs: set[str] = set()
        has_root_skill_md = False

        for info in all_entries:
            name = info.filename
            if name == "SKILL.md":
                has_root_skill_md = True
            parts = name.split("/")
            if len(parts) > 1 and parts[0]:
                top_level_dirs.add(parts[0])

        # Determine layout
        if has_root_skill_md:
            # Single-skill at root — all entries belong to this skill
            return [_parse_single_skill(zf, all_entries, "", max_per_file=max_per_file)]

        if not top_level_dirs:
            # No top-level dirs and no root SKILL.md — empty or unrecognized
            return [ParsedSkill(error="No SKILL.md found in skill")]

        # Check which top-level dirs contain a SKILL.md
        dirs_with_skill_md: list[str] = []
        for d in sorted(top_level_dirs):
            skill_md_path = f"{d}/SKILL.md"
            if skill_md_path in {info.filename for info in all_entries}:
                dirs_with_skill_md.append(d)

        if len(dirs_with_skill_md) == 0:
            # No SKILL.md anywhere
            return [ParsedSkill(error="No SKILL.md found in skill")]

        if len(dirs_with_skill_md) == 1 and len(top_level_dirs) == 1:
            # Single-named-dir layout
            skill_dir = dirs_with_skill_md[0]
            skill_root = f"{skill_dir}/"
            skill_entries = [info for info in all_entries if info.filename.startswith(skill_root) or info.filename == skill_root]
            return [_parse_single_skill(zf, skill_entries, skill_root, max_per_file=max_per_file)]

        # Bulk layout: each dir is its own skill
        # Entries that are NOT under any skill dir are ignored (no stray root files in bulk)
        results: list[ParsedSkill] = []
        for skill_dir in sorted(dirs_with_skill_md):
            skill_root = f"{skill_dir}/"
            skill_entries = [info for info in all_entries if info.filename.startswith(skill_root)]
            result = _parse_single_skill(zf, skill_entries, skill_root, max_per_file=max_per_file)
            results.append(result)

        return results
