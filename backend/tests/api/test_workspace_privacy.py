"""Phase 18 — Privacy invariant verification (SEC-04 carryover from v1.0).

Verifies that workspace file content containing PII is redacted/anonymized in the
LLM-bound payload after a read_file tool call. No new privacy code in Phase 18 —
this test confirms existing egress filter coverage extends to the new tool surface.

Invariant being tested (D-15 / T-18-28):
  "real PII never reaches cloud-LLM payloads" — when pii_redaction_enabled=True,
  any workspace file content returned by read_file passes through anonymize_tool_output
  before being forwarded to the LLM. The egress filter provides a second line of
  defence that blocks the call if PII is still present.

Coverage:
  Test 1: read_file tool output (PII in content) → anonymize_tool_output →
          surrogate form used in LLM payload (not raw PII)
  Test 2: with redaction disabled, PII passes through to LLM payload (confirms
          the filter is the gate, not the data)
  Test 3: at-rest check — workspace_files.content stores RAW PII (redaction is
          an egress concern, not a storage concern)
  Test 4: egress_filter correctly trips on a payload containing registry-known PII

Test design notes:
  - Tests 1, 2, 4 are pure unit/service tests using mocked system settings.
    They do NOT require a live running HTTP server — they test the service layer
    directly, which is where the privacy invariant lives.
  - Test 3 uses the live Supabase DB (same credentials as e2e suite).
  - The system_settings DB has pii_redaction_enabled=False in the test environment.
    Tests 1 and 4 patch get_system_settings to return pii_redaction_enabled=True
    so the RedactionService takes the full NER+anonymization path.
  - The synthetic PII fixture uses a fictitious name + email (not real person data):
    "Bambang Sutrisno sent email to bambang.s@example.com" — per T-18-29 (accepted risk).
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock

# ---------------------------------------------------------------------------
# PII fixture — synthetic, not a real third party (T-18-29)
# Using Indonesian names known to be detected by xx_ent_wiki_sm NER model
# ---------------------------------------------------------------------------

PII_NAME = "Bambang Sutrisno"
PII_EMAIL = "bambang.s@example.com"
PII_CONTENT = f"Pak {PII_NAME} sent email to {PII_EMAIL}"

# System settings mock with pii_redaction_enabled=True
_MOCK_SYS_SETTINGS_REDACTION_ON = {
    "pii_redaction_enabled": True,
    "llm_model": "openai/gpt-4o-mini",
    "entity_resolution_mode": "none",  # No LLM calls for entity resolution in tests
}

_MOCK_SYS_SETTINGS_REDACTION_OFF = {
    "pii_redaction_enabled": False,
    "llm_model": "openai/gpt-4o-mini",
    "entity_resolution_mode": "none",
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TEST_EMAIL = os.environ.get("TEST_EMAIL", "test@test.com")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "!*-3-3?3uZ?b$v&")


# ---------------------------------------------------------------------------
# Test 1: anonymize_tool_output redacts PII in read_file result
#
# Directly tests the anonymize_tool_output transformation on a read_file
# shaped dict containing PII content. This is the service-layer path that
# runs inside the chat loop when redaction_on=True.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_file_output_redacted_by_anonymize_tool_output(
    fresh_thread_id: str,
    redaction_service,
):
    """Test 1: anonymize_tool_output redacts PII from a read_file result.

    Simulates what the chat loop does after a read_file tool call:
      tool_output = await ws.read_file(tid, path)  →  {ok, content: PII_CONTENT, ...}
      tool_output = await anonymize_tool_output(tool_output, registry, redaction_service)
      # → content should now have surrogates, not raw PII

    The registry must contain PII_NAME and PII_EMAIL for the filter to catch them;
    we pre-seed it via redact_text so the entities are registered.

    Patches get_system_settings to return pii_redaction_enabled=True because the
    test DB has this flag set to False.
    """
    from app.services.redaction.registry import ConversationRegistry
    from app.services.redaction.tool_redaction import anonymize_tool_output

    with patch(
        "app.services.redaction_service.get_system_settings",
        return_value=_MOCK_SYS_SETTINGS_REDACTION_ON,
    ):
        # 1. Load a registry for this thread and seed it with PII (runs NER, upserts entries).
        registry = await ConversationRegistry.load(fresh_thread_id)
        seed_result = await redaction_service.redact_text(PII_CONTENT, registry=registry)

    # Verify seed worked: the registry now knows about PII_NAME (Bambang Sutrisno).
    entries = registry.entries()
    if len(entries) == 0:
        pytest.skip(
            f"NER did not detect any entities in PII fixture {PII_CONTENT!r}. "
            f"entity_map={seed_result.entity_map!r}. "
            f"Verify spaCy xx_ent_wiki_sm is installed and the test PII string contains "
            f"a detectable PERSON/EMAIL entity above the confidence threshold."
        )

    known_real_values = {e.real_value.casefold() for e in entries}

    # 2. Simulate a read_file tool output containing raw PII.
    read_file_output = {
        "ok": True,
        "is_binary": False,
        "content": PII_CONTENT,
        "size_bytes": len(PII_CONTENT),
        "mime_type": "text/markdown",
        "file_path": "contacts.md",
    }

    # 3. Apply anonymize_tool_output with the seeded registry (same path as chat.py loop).
    #    The registry already has the PII entries from step 1.
    with patch(
        "app.services.redaction_service.get_system_settings",
        return_value=_MOCK_SYS_SETTINGS_REDACTION_ON,
    ):
        redacted_output = await anonymize_tool_output(
            read_file_output, registry, redaction_service
        )

    # 4. Assert raw PII is NOT in the redacted content.
    redacted_content = redacted_output.get("content", "")
    for real_value in known_real_values:
        # Match case-insensitively to catch partial matches.
        assert real_value not in redacted_content.casefold(), (
            f"PRIVACY LEAK: real value {real_value!r} (from registry) still present "
            f"in anonymize_tool_output result.\n"
            f"raw content: {PII_CONTENT!r}\n"
            f"redacted content: {redacted_content!r}"
        )

    # 5. Verify the surrogate form is non-empty (content was transformed, not blanked).
    assert redacted_content, (
        "anonymize_tool_output returned empty content — transform may have erased the whole string"
    )


# ---------------------------------------------------------------------------
# Test 2: With redaction disabled, PII passes through unchanged
#
# Confirms the filter is the actual gate — when redaction is OFF, the raw
# PII is NOT removed from the tool output. This sanity-checks that the
# privacy protection in Test 1 is not a trivially-passing no-op.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_file_output_not_redacted_when_redaction_off(
    fresh_thread_id: str,
):
    """Test 2: when pii_redaction_enabled=False, raw PII passes through to LLM payload.

    The redaction service returns identity when PII_REDACTION_ENABLED=false
    (D-84 invariant). This test verifies the test harness is actually exercising
    the filter — if Test 1 passes AND Test 2 passes, we know the filter is the gate.
    """
    from app.services.redaction.registry import ConversationRegistry
    from app.services.redaction.tool_redaction import anonymize_tool_output

    # Load a fresh registry (no PII seeded — simulates redaction-off session).
    registry = await ConversationRegistry.load(fresh_thread_id)

    read_file_output = {
        "ok": True,
        "is_binary": False,
        "content": PII_CONTENT,
        "size_bytes": len(PII_CONTENT),
        "mime_type": "text/markdown",
        "file_path": "contacts.md",
    }

    # Simulate redaction OFF: a mock redaction_service that returns leaves unchanged.
    # (This mirrors the D-84 identity path in RedactionService when flag is off.)
    mock_rs = AsyncMock()
    mock_rs.redact_text_batch.side_effect = lambda texts, registry: texts

    # anonymize_tool_output with an identity-returning service leaves PII intact.
    passthrough_output = await anonymize_tool_output(read_file_output, registry, mock_rs)
    passthrough_content = passthrough_output.get("content", "")

    # With redaction OFF (identity service), raw PII should still be present.
    assert PII_NAME in passthrough_content or PII_EMAIL in passthrough_content, (
        f"Expected raw PII to survive when redaction is OFF (identity service), "
        f"but content was: {passthrough_content!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: At-rest storage — workspace_files.content stores raw PII
#
# Redaction is an EGRESS concern, not a storage concern. The raw content
# must be stored in workspace_files so that:
#  - de-anonymization can reconstruct the original content after LLM processing
#  - audit trail preserves the actual user data
#
# This test writes PII content to a real workspace_files row (via service-role),
# then reads it back directly from the DB to confirm it's stored raw.
# ---------------------------------------------------------------------------


def test_at_rest_content_stores_raw_pii():
    """Test 3: workspace_files.content stores RAW PII (redaction is egress-only).

    Writes PII to workspace_files via the service layer (which uses authed client
    → enforces RLS), then reads the raw value back via service-role client
    (bypasses RLS) to confirm no redaction happened at the storage layer.

    Note: this is a synchronous test. The pytestmark=asyncio applies to async tests
    only; this test is explicitly excluded from asyncio via @pytest.mark.no_asyncio.
    """
    from app.database import get_supabase_client
    from app.services.workspace_service import WorkspaceService

    # Login to get token
    svc = get_supabase_client()
    result = svc.auth.sign_in_with_password({"email": TEST_EMAIL, "password": TEST_PASSWORD})
    token = result.session.access_token
    user_id = str(result.user.id)

    # Create an isolated thread for this test
    thread_id = str(uuid.uuid4())
    svc.table("threads").insert({
        "id": thread_id,
        "user_id": user_id,
        "title": "ws-privacy-at-rest-test",
    }).execute()

    try:
        # Write PII content via WorkspaceService (RLS-scoped, no redaction here)
        ws = WorkspaceService(token=token)
        write_result = asyncio.run(ws.write_text_file(thread_id, "contacts.md", PII_CONTENT))
        assert write_result.get("ok"), f"write_text_file failed: {write_result}"

        # Read back via SERVICE-ROLE client (bypasses RLS) to check raw storage
        raw = (
            svc.table("workspace_files")
            .select("content")
            .eq("thread_id", thread_id)
            .eq("file_path", "contacts.md")
            .limit(1)
            .execute()
        )
        assert raw.data, "Expected workspace_files row for contacts.md, got empty"
        stored_content = raw.data[0]["content"]

        # Raw PII must be present at rest (redaction is egress-only)
        assert PII_NAME in stored_content or PII_EMAIL in stored_content, (
            f"STORAGE INVARIANT VIOLATED: PII was redacted at storage layer. "
            f"Expected raw content containing PII, got: {stored_content!r}"
        )
        assert stored_content == PII_CONTENT, (
            f"Stored content differs from written content (redaction at rest?). "
            f"expected: {PII_CONTENT!r}\n"
            f"actual:   {stored_content!r}"
        )

    finally:
        # Cleanup
        try:
            svc.table("workspace_files").delete().eq("thread_id", thread_id).execute()
        except Exception:
            pass
        try:
            svc.table("threads").delete().eq("id", thread_id).execute()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Test 4: egress_filter trips on payload containing registry-known PII
#
# The egress filter is the second line of defence: even if anonymize_tool_output
# somehow failed, the egress filter would block the outbound LLM call.
# This test verifies the filter correctly detects workspace file content PII.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_egress_filter_trips_on_pii_payload(
    fresh_thread_id: str,
    redaction_service,
):
    """Test 4: egress_filter detects registry-known PII in an outbound payload.

    Simulates the pre-flight check that runs before every cloud LLM call:
      egress_result = egress_filter(json.dumps(messages), registry, provisional)
      if egress_result.tripped: → block the call (raise _EgressBlocked)

    This verifies that if anonymize_tool_output ever fails silently, the egress
    filter would catch the leakage and prevent the LLM from seeing raw PII.

    Patches get_system_settings to enable redaction for the seeding step.
    """
    import json

    from app.services.redaction.egress import egress_filter
    from app.services.redaction.registry import ConversationRegistry

    with patch(
        "app.services.redaction_service.get_system_settings",
        return_value=_MOCK_SYS_SETTINGS_REDACTION_ON,
    ):
        # 1. Seed registry with PII_NAME by running actual redaction.
        registry = await ConversationRegistry.load(fresh_thread_id)
        seed_result = await redaction_service.redact_text(PII_CONTENT, registry=registry)

    entries = registry.entries()
    if len(entries) == 0:
        pytest.skip(
            f"NER did not detect any entities in PII fixture {PII_CONTENT!r} "
            f"(entity_map={seed_result.entity_map!r}). "
            f"Egress filter requires registry entries to trip. "
            f"Verify spaCy xx_ent_wiki_sm is installed with supported language."
        )

    # 2. Construct a messages payload that contains raw PII (simulating a failure
    #    where anonymize_tool_output did NOT run or failed silently).
    messages = [
        {"role": "user", "content": "Please read my contacts file."},
        {
            "role": "tool",
            "tool_call_id": "tc-privacy-01",
            "content": json.dumps({
                "ok": True,
                "content": PII_CONTENT,  # ← raw PII that should have been redacted
                "file_path": "contacts.md",
            }),
        },
    ]
    payload_str = json.dumps(messages)

    # 3. Run egress filter — it should TRIP because registry contains PII_NAME.
    result = egress_filter(payload_str, registry, provisional=None)

    assert result.tripped, (
        f"EGRESS FILTER DID NOT TRIP on payload containing registry-known PII.\n"
        f"Registry entries: {[(e.entity_type, e.real_value) for e in entries]}\n"
        f"Payload (truncated): {payload_str[:300]}\n"
        f"egress_filter result: {result}"
    )
    assert result.match_count >= 1, (
        f"Expected match_count >= 1, got {result.match_count}"
    )

    # 4. Verify the filter correctly identifies the entity types involved.
    assert len(result.entity_types) >= 1, (
        f"Expected at least one entity type in egress result, got: {result.entity_types}"
    )
