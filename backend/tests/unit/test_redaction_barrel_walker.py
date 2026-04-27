"""Phase 5 Plan 05-02 Task 3: redaction/__init__.py barrel re-exports.

Asserts the walker functions are reachable via
``from app.services.redaction import deanonymize_tool_args, anonymize_tool_output``
and that pre-existing Phase 1-4 re-exports remain intact.

Per the existing module docstring (lines 11-21 of redaction/__init__.py),
``RedactionService`` / ``RedactionResult`` / ``get_redaction_service`` MUST
NOT be re-exported here — that would re-enter the package mid-load through
the chain ``__init__ -> redaction_service -> anonymization -> detection ->
uuid_filter -> __init__``. This test guards that invariant.
"""

from __future__ import annotations

import inspect
import pathlib


class TestNewWalkerReExports:
    def test_deanonymize_importable_from_barrel(self):
        from app.services.redaction import deanonymize_tool_args
        assert inspect.iscoroutinefunction(deanonymize_tool_args)

    def test_anonymize_importable_from_barrel(self):
        from app.services.redaction import anonymize_tool_output
        assert inspect.iscoroutinefunction(anonymize_tool_output)


class TestPreExistingExportsPreserved:
    def test_redaction_error_still_exported(self):
        from app.services.redaction import RedactionError
        assert RedactionError is not None

    def test_conversation_registry_still_exported(self):
        from app.services.redaction import ConversationRegistry
        assert ConversationRegistry is not None

    def test_entity_mapping_still_exported(self):
        from app.services.redaction import EntityMapping
        assert EntityMapping is not None


class TestCircularImportGuard:
    """The existing docstring forbids re-exporting RedactionService etc."""

    def test_redaction_service_not_re_exported_via_barrel_init(self):
        """Defense: even if the symbol exists in `app.services.redaction_service`,
        the barrel `__init__` MUST NOT pull it in (circular-import guard)."""
        src = pathlib.Path("app/services/redaction/__init__.py").read_text()
        assert (
            "from app.services.redaction_service import RedactionService"
            not in src
        ), "barrel must not re-export RedactionService (circular-import)"
        assert (
            "from app.services.redaction_service import" not in src
        ), "barrel must not import from app.services.redaction_service"


class TestAllListExtended:
    def test_all_list_includes_new_walker_names(self):
        import app.services.redaction as barrel
        all_list = getattr(barrel, "__all__", None)
        assert all_list is not None, "__all__ must exist on the barrel"
        assert "deanonymize_tool_args" in all_list
        assert "anonymize_tool_output" in all_list

    def test_all_list_preserves_existing_names(self):
        import app.services.redaction as barrel
        all_list = barrel.__all__
        for required in ("RedactionError", "ConversationRegistry", "EntityMapping"):
            assert required in all_list, f"{required} dropped from __all__"
