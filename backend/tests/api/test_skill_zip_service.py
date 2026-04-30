"""
test_skill_zip_service.py — Unit tests for skill_zip_service (pure stdlib + PyYAML).

All tests use in-memory ZIPs (no network, no DB, no FastAPI).
Covers all 11 cases from 07-03-PLAN test coverage section.
"""

from __future__ import annotations

import io
import struct
import zipfile

import pytest

from app.services.skill_zip_service import (
    ParsedSkill,
    SkillFrontmatter,
    SkippedFile,
    build_skill_zip,
    parse_skill_zip,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_zip(files: dict[str, bytes | str]) -> bytes:
    """Build a raw ZIP in memory from a dict of path->content."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(path, content)
    return buf.getvalue()


def _fake_loader(storage_path: str) -> bytes:
    """Stub loader that returns predictable bytes for any path."""
    return f"content-of:{storage_path}".encode("utf-8")


def _minimal_skill_md(name: str = "my-skill", description: str = "A test skill", body: str = "# Instructions\n\nDo stuff.\n") -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n{body}"


# ---------------------------------------------------------------------------
# Test 1: Round-trip — build_skill_zip → parse_skill_zip
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_round_trip_preserves_frontmatter_and_files(self):
        skill = {
            "name": "my-skill",
            "description": "A sample skill",
            "license": "MIT",
            "instructions": "# My Skill\n\nThis skill does things.\n",
        }
        files = [
            {"relative_path": "scripts/helper.py", "storage_path": "storage/skills/helper.py"},
            {"relative_path": "references/readme.md", "storage_path": "storage/skills/readme.md"},
            {"relative_path": "assets/logo.png", "storage_path": "storage/skills/logo.png"},
        ]

        buf = build_skill_zip(skill, files, _fake_loader)
        zip_bytes = buf.read()

        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 1
        result = parsed[0]

        assert result.error is None
        assert result.frontmatter is not None
        assert result.frontmatter.name == "my-skill"
        assert result.frontmatter.description == "A sample skill"
        assert result.frontmatter.license == "MIT"
        assert result.instructions_md == "# My Skill\n\nThis skill does things.\n"
        assert len(result.files) == 3

        # Byte-equal file contents
        file_by_path = {f.relative_path: f.content for f in result.files}
        assert file_by_path["scripts/helper.py"] == _fake_loader("storage/skills/helper.py")
        assert file_by_path["references/readme.md"] == _fake_loader("storage/skills/readme.md")
        assert file_by_path["assets/logo.png"] == _fake_loader("storage/skills/logo.png")

    def test_round_trip_skill_md_starts_with_delimiter(self):
        skill = {"name": "test-skill", "description": "Test", "instructions": "body\n"}
        buf = build_skill_zip(skill, [], _fake_loader)
        zip_bytes = buf.read()

        # Read the raw SKILL.md from the ZIP and verify it starts with ---
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        skill_md_bytes = zf.read("SKILL.md")
        skill_md_text = skill_md_bytes.decode("utf-8")
        assert skill_md_text.startswith("---\n"), f"SKILL.md must start with '---\\n', got: {skill_md_text[:20]!r}"

    def test_round_trip_reparse_inner_skill_md(self):
        """Test 11: build -> parse -> re-parse inner SKILL.md text starts with ---."""
        skill = {"name": "round-trip", "description": "Round trip test", "instructions": "## Instructions\n\nDo stuff.\n"}
        buf = build_skill_zip(skill, [], _fake_loader)
        zip_bytes = buf.read()

        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        skill_md_text = zf.read("SKILL.md").decode("utf-8")
        assert skill_md_text.startswith("---\n")

        # parse the parsed result
        result = parse_skill_zip(zip_bytes)
        assert len(result) == 1
        assert result[0].error is None
        assert result[0].frontmatter is not None
        assert result[0].frontmatter.name == "round-trip"


# ---------------------------------------------------------------------------
# Test 2: Single-skill layouts
# ---------------------------------------------------------------------------

class TestSingleSkillLayouts:
    def test_skill_md_at_root(self):
        """SKILL.md at ZIP root — single-skill layout."""
        skill_md = _minimal_skill_md("root-skill", "Skill at root")
        zip_bytes = _make_zip({"SKILL.md": skill_md, "scripts/run.py": "print('hello')"})

        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 1
        result = parsed[0]
        assert result.error is None
        assert result.frontmatter is not None
        assert result.frontmatter.name == "root-skill"
        assert len(result.files) == 1
        assert result.files[0].relative_path == "scripts/run.py"

    def test_skill_md_in_named_subdir(self):
        """SKILL.md in named subdir — single-named-dir layout."""
        skill_md = _minimal_skill_md("named-skill", "Skill in named dir")
        zip_bytes = _make_zip({
            "named-skill/SKILL.md": skill_md,
            "named-skill/scripts/main.py": "print('ok')",
        })

        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 1
        result = parsed[0]
        assert result.error is None
        assert result.frontmatter is not None
        assert result.frontmatter.name == "named-skill"
        assert len(result.files) == 1
        assert result.files[0].relative_path == "scripts/main.py"


# ---------------------------------------------------------------------------
# Test 3: Bulk ZIP
# ---------------------------------------------------------------------------

class TestBulkZip:
    def test_bulk_three_skills(self):
        """3 skills: valid, bad name, missing required field."""
        valid_md = _minimal_skill_md("valid-skill", "A valid skill")
        bad_name_md = "---\nname: Invalid Name With Spaces\ndescription: bad\n---\n"
        missing_desc_md = "---\nname: no-description\n---\n"

        zip_bytes = _make_zip({
            "valid-skill/SKILL.md": valid_md,
            "invalid-name/SKILL.md": bad_name_md,
            "no-description/SKILL.md": missing_desc_md,
        })

        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 3

        by_error: list[ParsedSkill] = []
        valid_result: ParsedSkill | None = None
        for p in parsed:
            if p.error is None:
                valid_result = p
            else:
                by_error.append(p)

        # One valid skill
        assert valid_result is not None
        assert valid_result.frontmatter is not None
        assert valid_result.frontmatter.name == "valid-skill"
        assert len(valid_result.skipped_files) == 0

        # Two error skills
        assert len(by_error) == 2
        errors = {p.error for p in by_error}
        # bad name
        assert any("Invalid" in (e or "") for e in errors), f"Expected bad-name error, got: {errors}"
        # missing description
        assert any("description" in (e or "") for e in errors), f"Expected missing-desc error, got: {errors}"

        # skipped_files should be empty for all three (no per-file issues)
        for p in parsed:
            assert len(p.skipped_files) == 0


# ---------------------------------------------------------------------------
# Test 4: Per-file size limit (HIGH #5 regression)
# ---------------------------------------------------------------------------

class TestPerFileSizeLimit:
    def test_oversized_file_skipped_skill_kept(self):
        """11 MB file in assets → skipped; 9 MB file in references → kept."""
        skill_md = _minimal_skill_md("size-test", "Size test skill")
        # Use file_size metadata in ZipInfo by building manually
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
            zf.writestr("SKILL.md", skill_md)
            # 11 MB file (oversized)
            big = b"x" * (11 * 1024 * 1024)
            zf.writestr("assets/big.bin", big)
            # 9 MB file (within limit)
            ok = b"y" * (9 * 1024 * 1024)
            zf.writestr("references/ok.md", ok)
        zip_bytes = buf.getvalue()

        parsed = parse_skill_zip(zip_bytes, max_per_file=10 * 1024 * 1024, max_total=50 * 1024 * 1024)
        assert len(parsed) == 1
        result = parsed[0]

        assert result.error is None, f"Expected no error, got: {result.error}"
        assert len(result.files) == 1, f"Expected 1 file, got: {[f.relative_path for f in result.files]}"
        assert result.files[0].relative_path == "references/ok.md"
        assert len(result.skipped_files) == 1
        assert result.skipped_files[0].relative_path == "assets/big.bin"
        assert result.skipped_files[0].reason == "oversized"


# ---------------------------------------------------------------------------
# Test 5: Total size limit (ZIP-bomb defense)
# ---------------------------------------------------------------------------

class TestTotalSizeLimit:
    def test_total_size_raises_value_error(self):
        """51 MB uncompressed raises ValueError."""
        # Build a ZIP where uncompressed sum > 50 MB
        # Use zip stored so file_size is accurate
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
            skill_md = _minimal_skill_md("huge-skill", "Too large")
            zf.writestr("SKILL.md", skill_md)
            # 51 MB in assets
            huge = b"z" * (51 * 1024 * 1024)
            zf.writestr("assets/huge.bin", huge)
        zip_bytes = buf.getvalue()

        with pytest.raises(ValueError, match="ZIP exceeds 50 MB limit"):
            parse_skill_zip(zip_bytes)


# ---------------------------------------------------------------------------
# Test 6: Frontmatter edge cases
# ---------------------------------------------------------------------------

class TestFrontmatterEdgeCases:
    def test_missing_name(self):
        skill_md = "---\ndescription: No name here\n---\n# body\n"
        zip_bytes = _make_zip({"SKILL.md": skill_md})
        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 1
        assert parsed[0].error is not None
        assert "name" in parsed[0].error.lower()
        assert len(parsed[0].skipped_files) == 0

    def test_missing_description(self):
        skill_md = "---\nname: no-description\n---\n# body\n"
        zip_bytes = _make_zip({"SKILL.md": skill_md})
        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 1
        assert parsed[0].error is not None
        assert "description" in parsed[0].error.lower()
        assert len(parsed[0].skipped_files) == 0

    def test_malformed_yaml(self):
        skill_md = "---\nname: ok\ndescription: [\n---\n# body\n"
        zip_bytes = _make_zip({"SKILL.md": skill_md})
        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 1
        assert parsed[0].error is not None
        assert "malformed yaml" in parsed[0].error.lower()
        assert len(parsed[0].skipped_files) == 0

    def test_non_ascii_skill_name(self):
        skill_md = "---\nname: スキル\ndescription: Japanese name\n---\n# body\n"
        zip_bytes = _make_zip({"SKILL.md": skill_md})
        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 1
        assert parsed[0].error is not None
        # Error should mention ASCII or name
        assert len(parsed[0].skipped_files) == 0


# ---------------------------------------------------------------------------
# Test 7: Frontmatter delimiter (HIGH #4 regression)
# ---------------------------------------------------------------------------

class TestFrontmatterDelimiter:
    def test_missing_opening_delimiter_yields_error(self):
        """SKILL.md without a leading '---' line → ParsedSkill.error."""
        skill_md = "name: my-skill\ndescription: no delimiter\n---\n# body\n"
        zip_bytes = _make_zip({"SKILL.md": skill_md})
        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 1
        assert parsed[0].error is not None
        assert "frontmatter delimiter" in parsed[0].error.lower()

    def test_valid_delimiter_parses_correctly(self):
        """SKILL.md with proper delimiters must parse without error."""
        skill_md = _minimal_skill_md("valid-delim", "Valid delimiter")
        zip_bytes = _make_zip({"SKILL.md": skill_md})
        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 1
        assert parsed[0].error is None


# ---------------------------------------------------------------------------
# Test 8: Path traversal
# ---------------------------------------------------------------------------

class TestPathTraversal:
    def test_path_traversal_entry_goes_to_skipped(self):
        """ZIP with '../escape.md' entry — entry skipped, skill still created."""
        skill_md = _minimal_skill_md("safe-skill", "Safe skill")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("SKILL.md", skill_md)
            zf.writestr("scripts/good.py", "print('good')")
            # Path traversal entry — zipfile may normalize, so we inject manually
            # Use ZipInfo to write a traversal path
            info = zipfile.ZipInfo("../escape.md")
            zf.writestr(info, "evil content")
        zip_bytes = buf.getvalue()

        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 1
        result = parsed[0]
        assert result.error is None
        # escape.md should be in skipped_files with reason path_traversal
        skipped_paths = {s.relative_path: s.reason for s in result.skipped_files}
        assert any(r == "path_traversal" for r in skipped_paths.values()), f"Expected path_traversal skipped, got: {result.skipped_files}"
        # scripts/good.py should still be included
        assert any(f.relative_path == "scripts/good.py" for f in result.files)


# ---------------------------------------------------------------------------
# Test 9: Layout disambiguation (single vs bulk)
# ---------------------------------------------------------------------------

class TestLayoutDisambiguation:
    def test_root_skill_md_with_stray_readme_is_single(self):
        """SKILL.md at root + stray top-level README.md → single-skill (README in skipped)."""
        skill_md = _minimal_skill_md("root-skill", "Root skill")
        zip_bytes = _make_zip({
            "SKILL.md": skill_md,
            "README.md": "# Stray readme",
            "scripts/tool.py": "pass",
        })

        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 1
        result = parsed[0]
        assert result.error is None
        assert result.frontmatter is not None
        assert result.frontmatter.name == "root-skill"

        # README.md is outside layout
        skipped_reasons = {s.relative_path: s.reason for s in result.skipped_files}
        assert "README.md" in skipped_reasons
        assert skipped_reasons["README.md"] == "outside_layout"

        # scripts/tool.py should be in files
        assert any(f.relative_path == "scripts/tool.py" for f in result.files)


# ---------------------------------------------------------------------------
# Test 10: Outside layout
# ---------------------------------------------------------------------------

class TestOutsideLayout:
    def test_file_outside_allowed_prefixes_goes_to_skipped(self):
        """File at notes/private.md (not under scripts|references|assets) → skipped."""
        skill_md = _minimal_skill_md("layout-skill", "Layout test")
        zip_bytes = _make_zip({
            "SKILL.md": skill_md,
            "notes/private.md": "secret notes",
            "scripts/ok.py": "pass",
        })

        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 1
        result = parsed[0]
        assert result.error is None

        skipped_by_path = {s.relative_path: s.reason for s in result.skipped_files}
        assert "notes/private.md" in skipped_by_path
        assert skipped_by_path["notes/private.md"] == "outside_layout"

        assert len(result.files) == 1
        assert result.files[0].relative_path == "scripts/ok.py"


# ---------------------------------------------------------------------------
# Test: Non-ASCII file path (unicode in relative_path)
# ---------------------------------------------------------------------------

class TestNonAsciiFilePath:
    def test_non_ascii_file_path_goes_to_skipped(self):
        """File with unicode in relative path → skipped with reason='non_ascii_path'."""
        skill_md = _minimal_skill_md("ascii-skill", "ASCII skill")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("SKILL.md", skill_md)
            zf.writestr("scripts/good.py", "pass")
            # Write a file with unicode in its name
            unicode_path = "assets/ファイル.png"  # Japanese characters
            info = zipfile.ZipInfo(unicode_path)
            zf.writestr(info, b"png-content")
        zip_bytes = buf.getvalue()

        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 1
        result = parsed[0]
        assert result.error is None  # skill still created

        skipped_reasons = [s.reason for s in result.skipped_files]
        assert "non_ascii_path" in skipped_reasons

        # scripts/good.py still included
        assert any(f.relative_path == "scripts/good.py" for f in result.files)


# ---------------------------------------------------------------------------
# Test: Invalid skill name patterns
# ---------------------------------------------------------------------------

class TestSkillNameValidation:
    @pytest.mark.parametrize("bad_name", [
        "UPPERCASE",
        "has spaces",
        "-starts-with-dash",
        "ends-with-dash-",
        "double--dash",
        "123starts-with-number",
        "a" * 65,  # too long
        "has.dot",
        "has_underscore",
    ])
    def test_invalid_names_produce_error(self, bad_name: str):
        skill_md = f"---\nname: {bad_name!r}\ndescription: test\n---\nbody\n"
        zip_bytes = _make_zip({"SKILL.md": skill_md})
        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 1
        assert parsed[0].error is not None, f"Expected error for name {bad_name!r}"

    @pytest.mark.parametrize("good_name", [
        "my-skill",
        "a",
        "skill123",
        "my-skill-v2",
        "abc",
    ])
    def test_valid_names_parse_correctly(self, good_name: str):
        skill_md = f"---\nname: {good_name}\ndescription: test\n---\nbody\n"
        zip_bytes = _make_zip({"SKILL.md": skill_md})
        parsed = parse_skill_zip(zip_bytes)
        assert len(parsed) == 1
        assert parsed[0].error is None, f"Expected no error for name {good_name!r}, got: {parsed[0].error}"
        assert parsed[0].frontmatter is not None
        assert parsed[0].frontmatter.name == good_name


# Test 13: DB-style file dicts (filename key, no relative_path) — regression for Phase 07 export bug
# ---------------------------------------------------------------------------

class TestBuildSkillZipDbStyleFiles:
    """build_skill_zip must accept DB-row dicts that have 'filename' instead of 'relative_path'.

    The skill_files table stores a flattened 'filename' column (e.g. 'scripts__foo.py').
    The export router passes these rows directly to build_skill_zip, so the service must
    not KeyError when 'relative_path' is absent.
    """

    def test_db_style_filename_key_used_when_relative_path_absent(self):
        skill = {"name": "my-skill", "description": "A skill", "instructions": "body\n"}
        files = [
            {"filename": "scripts__helper.py", "storage_path": "storage/skills/helper.py"},
            {"filename": "references__readme.md", "storage_path": "storage/skills/readme.md"},
        ]
        buf = build_skill_zip(skill, files, _fake_loader)
        zf = zipfile.ZipFile(io.BytesIO(buf.read()))
        names = zf.namelist()
        assert "scripts__helper.py" in names
        assert "references__readme.md" in names

    def test_relative_path_preferred_over_filename_when_both_present(self):
        skill = {"name": "my-skill", "description": "A skill", "instructions": "body\n"}
        files = [
            {
                "relative_path": "scripts/helper.py",
                "filename": "scripts__helper.py",
                "storage_path": "storage/skills/helper.py",
            },
        ]
        buf = build_skill_zip(skill, files, _fake_loader)
        zf = zipfile.ZipFile(io.BytesIO(buf.read()))
        assert "scripts/helper.py" in zf.namelist()
        assert "scripts__helper.py" not in zf.namelist()
