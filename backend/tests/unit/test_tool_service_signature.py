"""Phase 5 Plan 05-02 Task 2: ToolService.execute_tool D-86 plumbing.

Asserts the signature changes shipped by Plan 05-02:

- ``execute_tool`` accepts a NEW keyword-only ``registry`` parameter.
- Default is ``None`` so existing positional callers are unaffected.
- The dispatch switch body is byte-identical to Phase 4 (D-91 invariant —
  ``tool_service`` stays redaction-unaware; the walker is centralized in
  the chat router).
- ``@traced(name="execute_tool")`` decorator name is unchanged (OBS audit
  continuity per Phase 1 D-16).
"""

from __future__ import annotations

import inspect
import pathlib
import re


class TestExecuteToolSignature:
    def test_registry_param_exists(self):
        from app.services.tool_service import ToolService

        sig = inspect.signature(ToolService.execute_tool)
        assert "registry" in sig.parameters, (
            f"registry param missing; got {list(sig.parameters.keys())}"
        )

    def test_registry_is_keyword_only(self):
        from app.services.tool_service import ToolService

        sig = inspect.signature(ToolService.execute_tool)
        param = sig.parameters["registry"]
        assert param.kind == inspect.Parameter.KEYWORD_ONLY, (
            f"registry must be keyword-only; got {param.kind}"
        )

    def test_registry_default_is_none(self):
        from app.services.tool_service import ToolService

        sig = inspect.signature(ToolService.execute_tool)
        param = sig.parameters["registry"]
        assert param.default is None, (
            f"registry default must be None for backward-compat; got {param.default!r}"
        )

    def test_existing_positional_params_preserved(self):
        """Phase 0 baseline shape is preserved: name, arguments, user_id, context."""
        from app.services.tool_service import ToolService

        sig = inspect.signature(ToolService.execute_tool)
        param_names = list(sig.parameters.keys())
        # `self` is not present on the unbound method via inspect for
        # functions defined in classes when called on the class itself —
        # but `Signature.parameters` for an unbound function via the class
        # DOES include `self`. Both cases are accepted by checking
        # containment rather than ordering of `self`.
        for required in ("name", "arguments", "user_id", "context"):
            assert required in param_names, (
                f"{required} missing from execute_tool; got {param_names}"
            )
        # Default for `context` is None
        assert sig.parameters["context"].default is None


class TestTracedDecoratorUnchanged:
    def test_execute_tool_traced_span_name_unchanged(self):
        src = pathlib.Path("app/services/tool_service.py").read_text()
        # Match either single or double quotes around the name
        pattern = r'@traced\(name=["\']execute_tool["\']\)'
        assert re.search(pattern, src), (
            "@traced(name='execute_tool') decorator missing or renamed"
        )


class TestDispatchSwitchUnchanged:
    """D-91: the dispatch switch body is byte-identical to Phase 4 — the
    walker is centralized in chat.py, not threaded into per-tool helpers.

    This test detects accidental per-tool wiring of `registry` inside the
    switch body.
    """

    def test_no_registry_threading_into_per_tool_helpers(self):
        src = pathlib.Path("app/services/tool_service.py").read_text()
        # Locate the execute_tool function body (rough heuristic — between
        # the @traced decorator and the next @traced decorator after it).
        match = re.search(
            r"@traced\(name=[\"\']execute_tool[\"\']\).*?async def execute_tool.*?(?=\n    @traced\b|\nclass\b|\Z)",
            src,
            re.DOTALL,
        )
        assert match, "could not locate execute_tool body"
        body = match.group(0)
        # No per-tool helper call should pass `registry=...`. The walker
        # invocation site is chat.py (Plan 05-04), not tool_service.
        assert "registry=registry" not in body, (
            "execute_tool must not thread registry into per-tool helpers (D-91)"
        )


class TestTypeCheckingImport:
    """The runtime annotation must be a string forward-reference; the actual
    import is gated under TYPE_CHECKING to avoid a runtime circular import
    via tool_service -> redaction -> ... -> tool_service.
    """

    def test_type_checking_block_imports_conversation_registry(self):
        src = pathlib.Path("app/services/tool_service.py").read_text()
        assert "TYPE_CHECKING" in src, "TYPE_CHECKING guard missing"
        # The TYPE_CHECKING-gated import line
        assert (
            "from app.services.redaction.registry import ConversationRegistry"
            in src
        ), "ConversationRegistry must be imported under TYPE_CHECKING"

    def test_registry_annotation_is_string_forward_ref(self):
        src = pathlib.Path("app/services/tool_service.py").read_text()
        # Look for the keyword-only `*,` followed by registry annotation as a string.
        # Accept any spacing.
        pattern = r"registry:\s*[\"\']ConversationRegistry"
        assert re.search(pattern, src), (
            "registry annotation must be a string forward-ref"
        )
