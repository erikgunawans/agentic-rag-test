"""Unit tests for sandbox_bridge_service — Phase 14 / BRIDGE-01, BRIDGE-03.

Tests:
  - Token lifecycle (create, validate, revoke)
  - validate_token rejects wrong user_id
  - validate_token rejects unknown token
  - _generate_stubs produces valid Python with correct function signatures
"""
import ast

import pytest

import app.services.sandbox_bridge_service as svc


@pytest.fixture(autouse=True)
def clear_token_store():
    """Reset _TOKEN_STORE before each test to prevent cross-test contamination."""
    svc._TOKEN_STORE.clear()
    yield
    svc._TOKEN_STORE.clear()


# ---------------------------------------------------------------------------
# Token lifecycle
# ---------------------------------------------------------------------------

class TestTokenLifecycle:
    def test_create_returns_nonempty_uuid_string(self):
        token = svc.create_bridge_token("thread-1", "user-a")
        assert isinstance(token, str)
        assert len(token) == 36  # UUID4 format with hyphens
        assert "-" in token

    def test_validate_correct_credentials_returns_true(self):
        token = svc.create_bridge_token("thread-1", "user-a")
        assert svc.validate_token(token, "user-a") is True

    def test_validate_wrong_user_id_returns_false(self):
        token = svc.create_bridge_token("thread-1", "user-a")
        assert svc.validate_token(token, "user-b") is False

    def test_validate_unknown_token_returns_false(self):
        assert svc.validate_token("no-such-token", "user-a") is False

    def test_token_create_validate_revoke(self):
        """Full lifecycle: create → validate → revoke → invalid."""
        token = svc.create_bridge_token("thread-1", "user-a")
        assert svc.validate_token(token, "user-a") is True
        svc.revoke_token("thread-1")
        assert svc.validate_token(token, "user-a") is False

    def test_revoke_noop_on_missing_thread(self):
        # Should not raise
        svc.revoke_token("nonexistent-thread")

    def test_multiple_threads_isolated(self):
        t1 = svc.create_bridge_token("thread-1", "user-a")
        t2 = svc.create_bridge_token("thread-2", "user-b")
        assert svc.validate_token(t1, "user-a") is True
        assert svc.validate_token(t2, "user-b") is True
        assert svc.validate_token(t1, "user-b") is False  # cross-user
        svc.revoke_token("thread-1")
        assert svc.validate_token(t1, "user-a") is False
        assert svc.validate_token(t2, "user-b") is True  # unaffected

    def test_create_overwrites_existing_token(self):
        """Calling create_bridge_token twice for same thread replaces old token."""
        t1 = svc.create_bridge_token("thread-1", "user-a")
        t2 = svc.create_bridge_token("thread-1", "user-a")
        assert t1 != t2  # new UUID generated
        assert svc.validate_token(t2, "user-a") is True
        assert svc.validate_token(t1, "user-a") is False  # old token gone


# ---------------------------------------------------------------------------
# Stub generation
# ---------------------------------------------------------------------------

class FakeToolDef:
    """Minimal ToolDefinition stand-in for testing stub generation."""
    def __init__(self, name, description, schema):
        self.name = name
        self.description = description
        self.schema = schema


class TestGenerateStubs:
    def _make_tool(self, name, params: dict, required: list[str] | None = None):
        return FakeToolDef(
            name=name,
            description=f"Tool {name}",
            schema={
                "type": "function",
                "function": {
                    "name": name,
                    "parameters": {
                        "type": "object",
                        "properties": params,
                        "required": required or [],
                    },
                },
            },
        )

    def test_generates_valid_python(self):
        tools = [
            self._make_tool("search_documents", {"query": {"type": "string"}}, ["query"]),
        ]
        code = svc._generate_stubs(tools)
        # Must be parseable Python
        tree = ast.parse(code)
        assert tree is not None

    def test_required_param_has_no_default(self):
        tools = [
            self._make_tool("search_documents", {"query": {"type": "string"}}, ["query"]),
        ]
        code = svc._generate_stubs(tools)
        assert "query: str" in code
        # Required params should NOT have `| None = None`
        assert "query: str | None = None" not in code

    def test_optional_param_has_none_default(self):
        tools = [
            self._make_tool("search_documents", {
                "query": {"type": "string"},
                "filter_tags": {"type": "array"},
            }, ["query"]),
        ]
        code = svc._generate_stubs(tools)
        assert "filter_tags: list[Any] | None = None" in code

    def test_no_params_generates_no_arg_function(self):
        tools = [self._make_tool("no_args_tool", {}, [])]
        code = svc._generate_stubs(tools)
        assert "def no_args_tool()" in code

    def test_stub_calls_client_call(self):
        tools = [
            self._make_tool("search_documents", {"query": {"type": "string"}}, ["query"]),
        ]
        code = svc._generate_stubs(tools)
        assert "_client.call('search_documents'" in code or '_client.call("search_documents"' in code

    def test_tool_client_import_in_header(self):
        code = svc._generate_stubs([])
        assert "from tool_client import ToolClient" in code

    def test_anyof_param_becomes_any(self):
        tools = [
            self._make_tool("complex_tool", {
                "val": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
            }, []),
        ]
        code = svc._generate_stubs(tools)
        assert "val: Any" in code

    def test_empty_tools_list_generates_valid_python(self):
        code = svc._generate_stubs([])
        tree = ast.parse(code)
        assert tree is not None

    def test_integer_param_type(self):
        tools = [
            self._make_tool("count_tool", {"limit": {"type": "integer"}}, ["limit"]),
        ]
        code = svc._generate_stubs(tools)
        assert "limit: int" in code

    def test_boolean_param_type(self):
        tools = [
            self._make_tool("flag_tool", {"active": {"type": "boolean"}}, ["active"]),
        ]
        code = svc._generate_stubs(tools)
        assert "active: bool" in code
