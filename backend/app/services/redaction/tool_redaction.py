"""Phase 5 D-91 / D-92: tool I/O symmetry walkers.

Recursive walkers over arbitrary JSON-shaped tool args (LLM -> real) and
tool outputs (real -> surrogate). Centralized so tool_service.py stays
tool-agnostic. Skip rules: UUID regex
(``^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$``) and
``len(s) < 3``.

Two public async entry points:

- ``deanonymize_tool_args(args, registry, redaction_service) -> dict``
  LLM-emitted surrogate-form args -> real values for tool execution.
  Pure registry lookup (no NER, no DB, no LLM); cannot raise.
- ``anonymize_tool_output(output, registry, redaction_service) -> Any``
  Real-form tool output -> surrogate-form for LLM consumption.
  Collect-then-batch leaf strategy: gather all leaf strings, run ONE
  ``redact_text_batch`` call (Plan 05-01 D-92 primitive — single
  ``asyncio.Lock`` acquisition), re-zip.

D-91 invariants:

- Recurse into dict / list / tuple ONLY; everything else returned identity.
- Skip rules applied at every leaf-string boundary (UUID + len<3).
- Recursion depth limit ``_MAX_DEPTH = 10`` levels; past the limit, return
  identity (soft fail per D-90-style operability).
- Return NEW structures (no in-place mutation; Phase 1 D-13/D-14
  immutability convention).
- NO logger calls (B4 invariant; ``@traced`` spans are the only
  observability surface — and they are decorator-managed, not opt-in).
- ``tool_service.py`` stays redaction-unaware (D-91): the walker is invoked
  by ``chat.py:_run_tool_loop`` (Plan 05-04), not by ``tool_service`` itself.

The de-anon direction is a Pass-1 longest-surrogate-first registry lookup
(mirrors ``redaction_service.py`` lines 855-885); the anon direction is a
two-phase walk:

1. Collect transformable leaves into a flat list while building a SHADOW
   tree where each transformable string is replaced by a marker tuple
   ``("__PII_LEAF__", idx)``.
2. Call ``redact_text_batch(collected, registry)`` ONCE — this is the
   Plan 05-01 D-92 primitive, which acquires the per-thread ``asyncio.Lock``
   for the full batch (single contention window, single DB upsert path).
3. Re-zip: walk the shadow tree, replacing each marker tuple with the
   anonymized string at its index.

See ``.planning/phases/05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co/05-CONTEXT.md``
(D-86, D-91, D-92) for the locked decisions that shape this module.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Mapping

from app.services.redaction.registry import ConversationRegistry
from app.services.tracing_service import traced

if TYPE_CHECKING:
    # ``RedactionService`` is referenced ONLY in type annotations. The
    # walker calls ``redaction_service.redact_text_batch(...)`` via the
    # passed-in instance (duck-typing), so the runtime import would only
    # introduce a circular import once this module is re-exported by
    # ``app.services.redaction.__init__`` (the barrel). The chain
    # ``redaction.__init__ -> tool_redaction -> redaction_service ->
    # anonymization -> ... -> redaction.__init__`` deadlocks unless we
    # gate this import under ``TYPE_CHECKING``. The same pattern is used
    # in ``app.services.tool_service`` for ``ConversationRegistry``.
    from app.services.redaction_service import RedactionService

# Strict UUID regex: lowercase hex, exact dash positions, fully anchored.
# Defense-in-depth complement to Phase 1 D-04 ``detect_entities`` UUID filter
# (UUIDs are short-circuited at both layers).
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

# Below this length, a leaf string is too short to contain meaningful PII
# and is returned identity — saves NER cost and avoids registry corruption
# on tokens like operators ("eq", "in"), enum tags, and 1–2-char acronyms.
_MIN_LEN = 3

# Recursion depth cap (Claude's discretion). Tools in this codebase emit
# JSON-serializable structures (no Python object cycles), so this is a guard
# against pathological LLM-emitted args / future tools, not real outputs.
# Past the limit the node is returned identity (no raise — D-90 soft fail).
_MAX_DEPTH = 10

# Marker tuple shape used by the anon walker's collect/re-zip phases.
# Chosen for trivial isinstance / equality detection without a class.
_MARKER_TAG = "__PII_LEAF__"


# ---------------------------------------------------------------------------
# De-anon direction (LLM surrogate-form args -> real values for tool exec)
# ---------------------------------------------------------------------------


def _deanon_leaf(s: str, registry: ConversationRegistry) -> str:
    """Pass-1 longest-surrogate-first registry transform for a single leaf.

    Mirrors ``redaction_service.py`` lines 855-885 (the canonical Pass-1
    algorithm shipped in Phase 4 D-71). Pure registry lookup — never raises,
    never calls NER, never touches the DB.

    Skip rules applied at the boundary:
      - UUID-shape (lowercase hex with strict dash positions) -> identity.
      - ``len(s) < _MIN_LEN`` -> identity.

    Sort key matches the parent module: longer surrogate wins (prevents
    partial-overlap corruption); on tie, longer real wins (keeps canonical
    real values winning over D-48 sub-surrogate variants).
    """
    if _UUID_RE.fullmatch(s) or len(s) < _MIN_LEN:
        return s
    entries_sorted = sorted(
        registry.entries(),
        key=lambda m: (len(m.surrogate_value), len(m.real_value)),
        reverse=True,
    )
    out = s
    for m in entries_sorted:
        # Defensive: skip empty values to avoid pathological re.escape("")
        # behavior (matches every position).
        if not m.surrogate_value or not m.real_value:
            continue
        out = re.sub(
            re.escape(m.surrogate_value),
            m.real_value,
            out,
            flags=re.IGNORECASE,
        )
    return out


def _deanon_walk(
    node: Any, registry: ConversationRegistry, depth: int
) -> Any:
    """Synchronous recursive walker for the de-anon direction (no async I/O).

    Recurses into dict / list / tuple ONLY. Past ``_MAX_DEPTH`` the node is
    returned identity (no raise). Bytes / ints / floats / bools / None /
    arbitrary objects are returned identity (Phase 1 D-13/D-14 immutability;
    no reflection, no ``__reduce__``, no ``__class__`` tricks).
    """
    if depth >= _MAX_DEPTH:
        return node
    if isinstance(node, dict):
        return {
            k: _deanon_walk(v, registry, depth + 1) for k, v in node.items()
        }
    if isinstance(node, list):
        return [_deanon_walk(v, registry, depth + 1) for v in node]
    if isinstance(node, tuple):
        return tuple(_deanon_walk(v, registry, depth + 1) for v in node)
    if isinstance(node, str):
        return _deanon_leaf(node, registry)
    return node


@traced(name="redaction.deanonymize_tool_args")
async def deanonymize_tool_args(
    args: Mapping[str, Any],
    registry: ConversationRegistry,
    redaction_service: RedactionService,
) -> dict[str, Any]:
    """LLM-emitted surrogate-form args -> real values for tool execution.

    Recursive walk; replaces each leaf string with its registry-real form
    via Pass-1 longest-surrogate-first transform. Pure lookup — no NER,
    no DB, no LLM call.

    Args:
        args: arbitrary JSON-shaped tool args from the LLM (typically a
            dict from ``openai_tool.function.arguments`` JSON-decode).
        registry: per-thread :class:`ConversationRegistry` (Plan 05-04
            caller's instance).
        redaction_service: unused on the de-anon path (kept for symmetry
            with :func:`anonymize_tool_output`'s signature; the Pass-1
            transform needs only the registry).

    Returns:
        A new dict (input never mutated) with surrogate strings replaced by
        real values; non-string leaves returned identity. UUID-shaped and
        ``len<3`` strings are returned identity at every leaf boundary.
    """
    # The async signature is intentional — keeps the walker symmetric with
    # ``anonymize_tool_output`` and lets the @traced span surface latency.
    # The body itself is pure (no awaits), so the cost is minimal.
    walked = _deanon_walk(args, registry, depth=0)
    # Type-narrow: the public contract returns ``dict[str, Any]`` for the
    # typical case where ``args`` is a dict. If the caller passes a non-dict
    # (e.g., a list at the top level — which the LLM will not do for OpenAI
    # tool-call ``arguments``), we still return whatever ``_walk`` produced.
    return walked  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Anon direction (real-form tool output -> surrogate-form for LLM)
# ---------------------------------------------------------------------------


@traced(name="redaction.anonymize_tool_output")
async def anonymize_tool_output(
    output: Any,
    registry: ConversationRegistry,
    redaction_service: RedactionService,
) -> Any:
    """Real-form tool output -> surrogate-form for LLM consumption.

    Collect-then-batch leaf strategy (D-91 + D-92): gather every
    transformable leaf string across the recursive structure, run ONE
    :meth:`RedactionService.redact_text_batch` call (single
    ``asyncio.Lock`` acquisition, single batched DB upsert), then re-zip
    the surrogate strings back into a NEW structure with the same shape
    as input.

    Args:
        output: arbitrary tool output (typically a dict — e.g.
            ``search_documents`` returns ``{"results": [...]}``,
            ``query_database`` returns ``{"rows": [...]}``).
        registry: per-thread :class:`ConversationRegistry`.
        redaction_service: required (the actual NER backend); calls
            ``redaction_service.redact_text_batch(collected, registry)`` once.

    Returns:
        A new structure (input never mutated) with leaf strings replaced
        by their surrogate forms; non-string leaves returned identity.
        Skip rules: UUID-shaped strings + ``len<3`` strings returned identity.
    """
    # Phase 1: walk and collect transformable leaves into ``leaves``,
    # building a SHADOW tree where each transformable string is replaced by
    # a marker tuple ``("__PII_LEAF__", idx)``. The marker is a tuple so
    # ``isinstance(_, tuple)`` continues to recurse (the re-zip phase
    # detects the marker shape before recursing into normal tuples).
    leaves: list[str] = []

    def _collect(node: Any, depth: int) -> Any:
        if depth >= _MAX_DEPTH:
            return node
        if isinstance(node, dict):
            return {k: _collect(v, depth + 1) for k, v in node.items()}
        if isinstance(node, list):
            return [_collect(v, depth + 1) for v in node]
        if isinstance(node, tuple):
            return tuple(_collect(v, depth + 1) for v in node)
        if isinstance(node, str):
            if _UUID_RE.fullmatch(node) or len(node) < _MIN_LEN:
                return node  # identity — skip rule
            idx = len(leaves)
            leaves.append(node)
            return (_MARKER_TAG, idx)  # marker tuple — re-zipped in phase 3
        return node

    shadow = _collect(output, depth=0)

    if not leaves:
        # Empty-leaves fast path — return input shape verbatim. No batch
        # call, no lock acquisition, no NER run. The caller cannot mutate
        # ``output`` through the result for the typical dict/list cases
        # because Python returns the same reference (no callers in the
        # chat loop mutate tool outputs after redaction).
        return output

    # Phase 2: ONE batched NER pass under ONE asyncio.Lock (Plan 05-01 D-92).
    anonymized = await redaction_service.redact_text_batch(leaves, registry)

    # Phase 3: re-zip — walk the shadow, replace each marker tuple with the
    # anonymized string at the recorded index. Real tuples are detected by
    # shape (length 2, first element ``_MARKER_TAG``, second element int);
    # any tuple that fails the shape test is recursed into normally.
    def _rezip(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: _rezip(v) for k, v in node.items()}
        if isinstance(node, list):
            return [_rezip(v) for v in node]
        if isinstance(node, tuple):
            if (
                len(node) == 2
                and node[0] == _MARKER_TAG
                and isinstance(node[1], int)
            ):
                return anonymized[node[1]]
            return tuple(_rezip(v) for v in node)
        return node

    return _rezip(shadow)


# ---------------------------------------------------------------------------
# Registry-filter direction (Fix D): real values → surrogates, no new registration
# ---------------------------------------------------------------------------


def _registry_filter_leaf(s: str, registry: ConversationRegistry) -> str:
    """Replace canonical real values in ``s`` with their surrogates.

    Uses ``registry.canonicals()`` (one entry per surrogate — the longest real
    value; consistent with the egress filter after Plan 05-07). Longest-first
    sort prevents partial-overlap corruption (e.g., "Pak Budi Sutomo" is
    replaced before "Pak Budi" so the full name is matched as a unit).

    Skip rules (UUID + len<3) mirror the other leaf helpers.
    """
    if _UUID_RE.fullmatch(s) or len(s) < _MIN_LEN:
        return s
    canonicals_sorted = sorted(
        registry.canonicals(),
        key=lambda m: len(m.real_value),
        reverse=True,
    )
    out = s
    for m in canonicals_sorted:
        if not m.real_value or not m.surrogate_value:
            continue
        out = re.sub(
            re.escape(m.real_value),
            m.surrogate_value,
            out,
            flags=re.IGNORECASE,
        )
    return out


def filter_tool_output_by_registry(
    output: Any,
    registry: ConversationRegistry,
) -> Any:
    """Replace registry-known real values in tool output with their surrogates.

    Fix D / ADR-0004 + ADR-0008: used for ``web_search`` output to prevent the
    user's own PII appearing incidentally in Tavily results from reaching the
    LLM unmasked — without the side-effect of registering Tavily public figures
    as new PII entities (which was the root cause of the egress-filter false
    positives fixed by Fix C).

    Key invariant: this function NEVER calls ``redact_text_batch`` — no NER,
    no asyncio.Lock, no DB write, no new entity registration.

    Residual limitation (Codex [P2]): if a Faker-generated surrogate coincidentally
    matches a real public figure's name in Tavily results, ``de_anonymize_text``
    will still map that name back to the user's real value in the synthesis
    response. A complete fix requires surrogate-collision detection at generation
    time or post-synthesis correction — out of scope for Fix D.

    Pure registry lookup. Synchronous (no async I/O needed).
    """
    def _walk(node: Any, depth: int) -> Any:
        if depth >= _MAX_DEPTH:
            return node
        if isinstance(node, dict):
            return {k: _walk(v, depth + 1) for k, v in node.items()}
        if isinstance(node, list):
            return [_walk(v, depth + 1) for v in node]
        if isinstance(node, tuple):
            return tuple(_walk(v, depth + 1) for v in node)
        if isinstance(node, str):
            return _registry_filter_leaf(node, registry)
        return node

    return _walk(output, depth=0)
