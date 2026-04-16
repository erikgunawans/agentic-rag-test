# Graph Question List

Live document. Updated alongside project development. Each question is designed to extract high-impact insight from the LexCore knowledge graph (895 nodes, 1,176 edges, 108 communities).

Run any question: `/graphify query "<question>"` or `/graphify path "A" "B"`

Last updated: 2026-04-17

---

## 1. Architecture & God Nodes

These questions target the most connected nodes. Changes here have the widest blast radius.

| # | Question | Command | Why It Matters |
|---|----------|---------|----------------|
| 1.1 | Why does `get_supabase_client()` bridge 6 communities? | `query` | 45 edges, betweenness 0.036. Any bug here breaks admin settings, approvals, RAG, ingestion, regulatory, and Google export simultaneously. |
| 1.2 | What are all callers of `get_supabase_authed_client()`? | `query` | 46 edges. Every user-scoped operation depends on this. Missing it on a new endpoint = RLS bypass. |
| 1.3 | What would break if `log_action()` had a bug? | `query` | 38 edges across approvals, admin, regulatory, integrations. Audit trail is a compliance requirement. |
| 1.4 | How does `apiFetch()` connect the frontend to every backend feature? | `query` | 25 edges. Single point of failure for all frontend API calls. Token refresh, error handling, CORS all live here. |
| 1.5 | Which functions depend on `get_system_settings()` and would break during a cache miss? | `query` | 60s TTL cache. Every chat request, document tool, and agent classification reads this. |

## 2. Data Flow & Pipeline Tracing

These trace the actual execution path through the system. Use `/graphify path` for shortest-path analysis.

| # | Question | Command | Why It Matters |
|---|----------|---------|----------------|
| 2.1 | How does a user message travel from `MessageInput` to `stream_chat()` to SSE response? | `path "MessageInput" "stream_chat"` | End-to-end chat flow. Any break in this chain = chat is down. |
| 2.2 | How does a file upload reach `document_chunks` with embeddings? | `path "FileUpload" "document_chunks"` | Ingestion pipeline: upload → storage → parse → chunk → embed → store. |
| 2.3 | How does `HybridRetrievalService` connect to the chat streaming output? | `path "HybridRetrievalService" "collect_sse_events"` | RAG retrieval → tool result → LLM response. The core value chain. |
| 2.4 | What path connects `classify_intent()` to `search_documents`? | `path "classify_intent" "search_documents"` | Agent routing → tool selection → retrieval. Multi-agent decision path. |
| 2.5 | How does `OpenRouterService` connect to both chat and document tools? | `query "OpenRouterService connections"` | Single LLM client serving two different patterns (streaming vs JSON). |

## 3. Security & Compliance

Critical for a legal platform handling sensitive documents.

| # | Question | Command | Why It Matters |
|---|----------|---------|----------------|
| 3.1 | Which endpoints use `get_supabase_client()` (service-role) but should use `get_supabase_authed_client()`? | `query` | Service-role bypasses RLS. Each usage needs justification. |
| 3.2 | Are there any routes missing `get_current_user` dependency? | `query "routes without get_current_user"` | Unprotected endpoints = unauthorized access to legal documents. |
| 3.3 | Which mutations are missing `log_action()` calls? | `query "mutations without log_action"` | Audit gap = compliance violation for Indonesian legal platform. |
| 3.4 | What connects `AdminGuard` to `require_admin` across frontend/backend? | `path "AdminGuard" "require_admin"` | RBAC enforcement consistency. Frontend guard without backend check = bypassable. |
| 3.5 | How isolated are user documents from each other in the graph? | `query "document isolation RLS"` | Row-Level Security verification. User A must never see User B's data. |

## 4. Testing Coverage

Cross-reference test nodes against feature nodes to find gaps.

| # | Question | Command | Why It Matters |
|---|----------|---------|----------------|
| 4.1 | Which communities have zero test coverage? | `query "communities without tests"` | 37 isolated communities (1 node each). Many are UI components with no test. |
| 4.2 | Does the test suite cover the full chat streaming pipeline? | `query "test coverage for SSE streaming"` | CHAT-01 through CHAT-06 exist, but do they cover agent routing + tool calling + streaming together? |
| 4.3 | Are document tools (create/compare/compliance/analyze) tested? | `query "document tool test coverage"` | LLM e2e test validated manually, but no automated tests exist for these endpoints. |
| 4.4 | What's the test coverage for the hybrid retrieval pipeline? | `query "HYB test coverage"` | HYB-01 through HYB-08 exist. Do they cover the RRF fusion + reranking path? |
| 4.5 | Which security tests (SEC-*) exist and what gaps remain? | `query "security test coverage"` | SEC-01 through SEC-05 cover RLS isolation. Missing: admin endpoint protection, token expiry. |

## 5. Dependency Risk & Coupling

Identify fragile connections and tightly coupled modules.

| # | Question | Command | Why It Matters |
|---|----------|---------|----------------|
| 5.1 | What are the 228 INFERRED edges and how many are actually correct? | `query "INFERRED edges verification"` | 228 model-guessed connections. False positives mislead architecture understanding. |
| 5.2 | Which node removal would disconnect the most communities? | `query "critical bridge nodes"` | `get_supabase_client()` has betweenness 0.036. Removing it disconnects 6 communities. |
| 5.3 | Are there circular dependencies between communities? | `query "circular dependencies"` | Community 0 (Approvals) and Community 2 (Admin) share many edges. Circular = refactor risk. |
| 5.4 | Which frontend components depend on more than 3 backend services? | `query "frontend backend coupling"` | High coupling = hard to change. Chat page likely touches chat, threads, documents, settings. |
| 5.5 | What's the longest dependency chain in the backend? | `query --dfs "longest dependency chain"` | Deep chains = cascading failure risk. DFS traces the deepest path. |

## 6. Feature Impact Analysis

Before building Phase 3, understand what existing code gets affected.

| # | Question | Command | Why It Matters |
|---|----------|---------|----------------|
| 6.1 | What would Phase 3 (Point-in-Time Compliance) need to connect to? | `query "compliance framework connections"` | Compliance check already uses OJK/GDPR. Point-in-time adds temporal dimension to existing nodes. |
| 6.2 | What would UU PDP Toolkit need to integrate with? | `query "UU PDP data protection connections"` | Touches compliance checking, document analysis, possibly new regulatory sources. |
| 6.3 | How would adding a new document tool affect the existing `document_tool_service.py`? | `explain "document_tool_service.py"` | 15 edges. New tools follow the `_llm_json()` pattern. Impact: Pydantic models, confidence gating, audit logging. |
| 6.4 | If we add real-time collaboration, which communities are affected? | `query "real-time collaboration impact"` | Touches Supabase Realtime (already used for doc status), chat state, document editing. |
| 6.5 | What's the impact of switching from OpenRouter to a different LLM provider? | `explain "OpenRouterService"` | 13 edges. Used by chat streaming, document tools, metadata extraction. Single swap point (good design). |

## 7. Design System & Frontend

UI architecture questions for design consistency.

| # | Question | Command | Why It Matters |
|---|----------|---------|----------------|
| 7.1 | How many frontend components are completely isolated (no connections)? | `query "isolated frontend components"` | 37 communities have only 1 node. Many are UI components that could be dead code. |
| 7.2 | What connects the Icon Rail to all page components? | `explain "IconRail"` | Navigation hub. Every page is reachable from here. Changes affect all routes. |
| 7.3 | How does the theme system (`ThemeContext`) propagate to all components? | `query "ThemeContext propagation"` | Light/dark/system theme. CSS vars in `:root` and `.dark`. Missing a component = broken theme. |
| 7.4 | Which pages share the most components? | `query "shared component usage across pages"` | Reuse patterns. If 5 pages use `FeaturePageLayout`, changes there ripple everywhere. |
| 7.5 | What's the relationship between `useChatState` and `MessageView`? | `path "useChatState" "MessageView"` | State management → rendering pipeline. SSE events → streaming text → tool cards. |

## 8. Cross-Cutting Concerns

Questions that span multiple communities and reveal systemic patterns.

| # | Question | Command | Why It Matters |
|---|----------|---------|----------------|
| 8.1 | What connects the research findings (PJAA) to actual shipped features? | `path "Opportunity 3: Intelligent Drafting Workbench" "Phase 4: Legal Domain Focus"` | Research → product validation. Shows which research insights became features. |
| 8.2 | How does the Indonesian localization system connect to every page? | `query "i18n coverage across pages"` | i18n touches every user-facing string. Missing keys = broken UI in one language. |
| 8.3 | What's the relationship between the PRD modules and the actual codebase? | `query "PRD module implementation mapping"` | Traceability: requirements → code. Are all 8 modules fully implemented? |
| 8.4 | Which architectural decisions (rationale nodes) have the most downstream impact? | `query "rationale nodes with most connections"` | "No LangChain" and "OpenRouter for flexibility" shape the entire backend. |
| 8.5 | What connects the admin review queue to document tool confidence gating? | `path "review-queue" "confidence_score"` | When confidence < 0.85 → pending_review → admin must approve. The trust pipeline. |

---

## How to Use This Document

1. **Before building a feature**: Run questions from section 6 to understand impact
2. **During code review**: Run questions from sections 3 and 5 to check for security/coupling
3. **After shipping**: Run questions from section 4 to identify test gaps
4. **During planning**: Run questions from sections 1 and 2 to understand architecture
5. **After graphify update**: Re-run high-value questions to see what changed

## Maintaining This Document

- Add new questions when new features are planned or shipped
- Mark questions as "Answered" with date and key finding after running them
- Remove questions that become irrelevant after architectural changes
- Re-run `/graphify --update` after significant code changes to keep the graph current
