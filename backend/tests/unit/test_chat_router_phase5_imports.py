"""Phase 5 Plan 05-04 Task 1: chat.py imports + EgressBlockedAbort + singletons.

Asserts the Phase 5 wiring scaffolding is in place at chat.py module level:
- EgressBlockedAbort exception class is defined and is a subclass of Exception.
- All Phase 5 imports resolve from chat.py (ConversationRegistry, walker fns,
  egress_filter, get_redaction_service, LLMProviderClient).
- The module-level _llm_provider_client singleton exists and is an
  LLMProviderClient instance.
- The router still imports cleanly (PostToolUse import-check parity).

Off-mode regression: this is a pure-imports task. With
PII_REDACTION_ENABLED=true (default) the chat router still works because
the imported symbols are not yet wired into stream_chat.
"""
from __future__ import annotations

import inspect


class TestPhase5ImportsAtModuleLevel:
    def test_egress_blocked_abort_class_defined(self):
        from app.routers.chat import EgressBlockedAbort
        assert inspect.isclass(EgressBlockedAbort)
        assert issubclass(EgressBlockedAbort, Exception)

    def test_egress_blocked_abort_can_raise_and_catch(self):
        from app.routers.chat import EgressBlockedAbort
        try:
            raise EgressBlockedAbort("test")
        except EgressBlockedAbort as exc:
            assert "test" in str(exc)

    def test_conversation_registry_imported(self):
        # via barrel re-export — confirms Plan 05-02 wiring is reachable
        # from the chat router.
        from app.routers import chat
        assert hasattr(chat, "ConversationRegistry")

    def test_walker_functions_imported(self):
        from app.routers import chat
        assert hasattr(chat, "deanonymize_tool_args")
        assert hasattr(chat, "anonymize_tool_output")

    def test_egress_filter_imported(self):
        from app.routers import chat
        assert hasattr(chat, "egress_filter")

    def test_get_redaction_service_imported(self):
        from app.routers import chat
        assert hasattr(chat, "get_redaction_service")

    def test_llm_provider_client_class_imported(self):
        from app.routers import chat
        assert hasattr(chat, "LLMProviderClient")


class TestModuleSingleton:
    def test_llm_provider_client_singleton_exists(self):
        from app.routers.chat import _llm_provider_client, LLMProviderClient
        assert isinstance(_llm_provider_client, LLMProviderClient)


class TestRouterImportClean:
    def test_chat_router_still_imports(self):
        from app.routers.chat import router
        assert router is not None

    def test_main_app_still_imports(self):
        from app.main import app
        assert app is not None
