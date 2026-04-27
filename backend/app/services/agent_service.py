import json
import logging
from typing import TYPE_CHECKING

from app.services.tracing_service import traced
from app.models.agents import AgentDefinition, OrchestratorResult
from app.config import get_settings
from app.services.redaction.egress import egress_filter
from app.services.redaction.prompt_guidance import get_pii_guidance_block
from app.services.system_settings_service import get_system_settings

if TYPE_CHECKING:
    from app.services.redaction.registry import ConversationRegistry

logger = logging.getLogger(__name__)

# Phase 4 D-79: single-source-of-truth PII guidance suffix. Module-import-time
# binding is correct under Phase 5 D-83's static-process-lifetime contract.
# Plan 05-08: sourced from system_settings DB column (admin-toggleable, 60s
# cached). Module-level evaluation reads the DB value at startup — changes
# to the toggle take effect within the 60s cache TTL on subsequent requests.
_PII_GUIDANCE = get_pii_guidance_block(
    redaction_enabled=bool(get_system_settings().get("pii_redaction_enabled", True)),
)

RESEARCH_AGENT = AgentDefinition(
    name="research",
    display_name="Research Agent",
    system_prompt=(
        "You are a thorough document research specialist. Your job is to find and "
        "synthesize information from the user's uploaded documents.\n\n"
        "Strategy:\n"
        "1. Search with the user's exact terms first\n"
        "2. If results are sparse, reformulate the query and search again\n"
        "3. Synthesize findings across multiple chunks\n"
        "4. Always cite the source filename when referencing information\n"
        "5. If documents don't contain the answer, say so clearly\n\n"
        "Be precise and cite your sources."
    ) + _PII_GUIDANCE,
    tool_names=["search_documents"],
    max_iterations=5,
)

DATA_ANALYST_AGENT = AgentDefinition(
    name="data_analyst",
    display_name="Data Analyst",
    system_prompt=(
        "You are a data analyst specializing in document metadata queries. You write "
        "SQL queries against the user's document collection.\n\n"
        "Rules:\n"
        "1. Always include WHERE user_id = :user_id in every query\n"
        "2. Only use SELECT statements — no writes\n"
        "3. Available columns: id, filename, file_size, mime_type, status, "
        "chunk_count, created_at, metadata->>'title', metadata->>'author', "
        "metadata->>'category', metadata->>'tags', metadata->>'summary', "
        "metadata->>'date_period'\n"
        "4. Present results clearly — use tables or lists for multiple rows\n"
        "5. If the first query doesn't answer the question, refine and try again\n"
    ) + _PII_GUIDANCE,
    tool_names=["query_database"],
    max_iterations=5,
)

GENERAL_AGENT = AgentDefinition(
    name="general",
    display_name="General Assistant",
    system_prompt=(
        "You are a helpful general assistant. Handle greetings, general knowledge "
        "questions, and conversations that don't require document search or database "
        "queries.\n\n"
        "If the user's question might benefit from current information, use web search. "
        "Otherwise, answer directly from your knowledge.\n"
        "Be concise and friendly."
    ) + _PII_GUIDANCE,
    tool_names=["web_search"],
    max_iterations=3,
)

EXPLORER_AGENT = AgentDefinition(
    name="explorer",
    display_name="Knowledge Base Explorer",
    system_prompt=(
        "You are a knowledge base explorer. Your job is to help the user navigate, "
        "browse, and understand the structure and content of their uploaded documents.\n\n"
        "Strategy:\n"
        "1. Use kb_tree to understand the overall folder structure\n"
        "2. Use kb_list_files to explore specific folders\n"
        "3. Use kb_glob to find documents by name patterns (e.g. '*.pdf', 'kontrak-*')\n"
        "4. Use kb_grep to search for specific text or regex patterns across all documents\n"
        "5. Use kb_read to read a document's content (chunk by chunk for large docs)\n\n"
        "For large documents, read in chunk ranges rather than all at once. "
        "Always tell the user which document and chunk range you examined. "
        "Present findings clearly with document names and folder locations."
    ) + _PII_GUIDANCE,
    tool_names=["kb_list_files", "kb_tree", "kb_grep", "kb_glob", "kb_read"],
    max_iterations=8,
)

AGENT_REGISTRY: dict[str, AgentDefinition] = {
    "research": RESEARCH_AGENT,
    "data_analyst": DATA_ANALYST_AGENT,
    "general": GENERAL_AGENT,
    "explorer": EXPLORER_AGENT,
}

CLASSIFICATION_PROMPT = (
    "You are an intent classifier. Given the user's message, decide which specialist "
    "agent should handle it. Respond with JSON only.\n\n"
    "Agents:\n"
    '- "research": Questions about content IN the user\'s uploaded documents. '
    "E.g. 'what do my docs say about X?', 'find info about Y in my files', "
    "'summarize the document about Z'.\n"
    '- "explorer": Browsing, navigating, or structurally exploring the knowledge base. '
    "E.g. 'show me my folder tree', 'list files in the contracts folder', "
    "'find all PDF files', 'search for the word arbitrase in my documents', "
    "'read the content of document X', 'what folders do I have?'.\n"
    '- "data_analyst": Questions about document METADATA — counts, sizes, categories, '
    "file lists. E.g. 'how many documents do I have?', 'which docs are about finance?', "
    "'what is my largest file?'.\n"
    '- "general": Greetings, general knowledge, current events, or anything that '
    "doesn't need the user's documents. E.g. 'hello', 'what is Python?', "
    "'what's the weather?'.\n\n"
    'Respond with: {"agent": "<name>", "reasoning": "<one sentence>"}'
)


@traced(name="get_agent")
def get_agent(name: str) -> AgentDefinition:
    """Look up an agent by name."""
    if name not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {name}")
    return AGENT_REGISTRY[name]


@traced(name="get_agent_tools")
def get_agent_tools(agent: AgentDefinition, all_tools: list[dict]) -> list[dict]:
    """Filter tools to only those the agent is allowed to use."""
    return [
        t for t in all_tools
        if t["function"]["name"] in agent.tool_names
    ]


@traced(name="classify_intent")
async def classify_intent(
    message: str,            # Phase 5 D-93: caller passes anonymized body.message
    history: list[dict],     # Phase 5 D-93: caller passes anonymized history items
    openrouter_service,
    model: str,
    *,
    registry: "ConversationRegistry | None" = None,  # Phase 5 D-94 (egress filter context)
) -> OrchestratorResult:
    """Classify user intent via a single LLM call.

    Phase 5 contract (D-93 / D-94 / D-96):
    - Caller (chat.py event_generator) passes ALREADY-anonymized message +
      history items. The D-93 batch chokepoint upstream owns the
      anonymization; this function does NOT touch the registry's lock.
    - When ``registry is not None`` and ``pii_redaction_enabled=True``, a
      pre-flight egress filter wraps the LLM call as defense-in-depth
      against an upstream Phase 1 NER miss (T-05-03-1 mitigation). On trip,
      returns ``OrchestratorResult(agent='general', reasoning='egress_blocked')``
      and emits a B4-compliant warning log (counts only — no payload, no
      entity values, no surrogates).
    - When ``registry is None`` (legacy callers, off-mode, or test fixtures
      that don't pass a registry): the egress wrapper is SKIPPED — function
      behaves identically to Phase 0 baseline (SC#5 invariant).
    - Return contract is UNCHANGED: ``OrchestratorResult`` carries a PII-free
      agent enum string; ``reasoning`` is internal-only (not externalized
      via SSE per Phase 4 baseline).
    """
    # Keep classification prompt small — only last 3 history messages
    recent_history = history[-3:] if len(history) > 3 else history
    messages = [
        {"role": "system", "content": CLASSIFICATION_PROMPT},
        *[{"role": m["role"], "content": m["content"]} for m in recent_history if m.get("content")],
        {"role": "user", "content": message},
    ]

    try:
        # Phase 5 D-94: pre-flight egress filter (defense-in-depth; covers
        # Plan 05-04 upstream NER misses). Skipped when redaction is OFF
        # (D-83 global gate) or no registry passed (legacy callers + test
        # fixtures). T-05-03-4 mitigation: NO try/except around egress_filter
        # itself — exceptions propagate to the existing outer try/except,
        # which fails CLOSED (returns the 'general' fallback).
        # Plan 05-08: redaction toggle read from system_settings (DB-backed).
        if registry is not None and bool(get_system_settings().get("pii_redaction_enabled", True)):
            payload = json.dumps(messages, ensure_ascii=False)
            # D-94: provisional set is empty by the time classify_intent
            # runs because D-93's history batch already commits new entities
            # to DB before any cloud LLM contact. egress_filter accepts the
            # value positionally as `provisional`.
            provisional_surrogates = None
            egress_result = egress_filter(payload, registry, provisional_surrogates)
            if egress_result.tripped:
                # B4 invariant (T-05-03-2): counts only — never payload,
                # entity values, or surrogates. Format mirrors Phase 3 D-55.
                logger.warning(
                    "egress_blocked event=egress_blocked feature=classify_intent "
                    "entity_count=%d",
                    egress_result.match_count,
                )
                return OrchestratorResult(
                    agent="general",
                    reasoning="egress_blocked",
                )

        result = await openrouter_service.complete_with_tools(
            messages,
            tools=None,
            model=model,
            response_format={"type": "json_object"},
        )
        content = result.get("content", "")
        parsed = json.loads(content)
        return OrchestratorResult(
            agent=parsed.get("agent", "general"),
            reasoning=parsed.get("reasoning", ""),
        )
    except Exception as e:
        logger.warning("Intent classification failed: %s — falling back to general", e)
        return OrchestratorResult(agent="general", reasoning="fallback")
