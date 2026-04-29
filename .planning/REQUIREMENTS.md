# Requirements: LexCore v1.1 — Agent Skills & Code Execution

## Milestone Goal

Transform LexCore's chat interface into a customizable AI agent platform where users create and manage reusable skills, attach resource files to those skills, execute sandboxed Python code, and maintain persistent tool memory across conversation turns.

---

## v1.1 Requirements

### Agent Skills Core (SKILL-*)

- [ ] **SKILL-01**: User can create a skill with name, description, and instructions via a form dialog
- [ ] **SKILL-02**: User can trigger AI-guided skill creation that uses the built-in `skill-creator` skill conversationally via chat
- [ ] **SKILL-03**: User can browse all visible skills (own + global) in a searchable list with global/disabled badges
- [ ] **SKILL-04**: User can edit skill properties (name, description, instructions) and toggle enabled/disabled
- [ ] **SKILL-05**: User can delete their own private skills
- [ ] **SKILL-06**: User can toggle a skill between private and global (share/unshare with all users)
- [ ] **SKILL-07**: System injects enabled skills as a lightweight name/description catalog into the LLM system prompt
- [ ] **SKILL-08**: LLM can call `load_skill` tool to fetch full instructions when user query matches a skill description
- [ ] **SKILL-09**: LLM can call `save_skill` tool to persist a new skill after AI-guided creation flow
- [ ] **SKILL-10**: A global `skill-creator` seed skill is created during setup/migration
- [ ] **SKILL-11**: A "Skills" tab appears in top navigation alongside Chat and Documents

### Skill Building-Block Files (SFILE-*)

- [ ] **SFILE-01**: User can upload files to a skill from the skill editor (own skills only)
- [ ] **SFILE-02**: `load_skill` tool response includes a table of attached files (name, size, type)
- [ ] **SFILE-03**: LLM can call `read_skill_file` tool to fetch content of a specific skill-attached file
- [ ] **SFILE-04**: User can preview text file content in a slide-in panel with copy and download buttons
- [ ] **SFILE-05**: User can delete files attached to their own skills

### Code Execution Sandbox (SANDBOX-*)

- [ ] **SANDBOX-01**: LLM can execute Python code in a sandboxed Docker container via `execute_code` tool
- [ ] **SANDBOX-02**: Python session persists variables across `run()` calls within a thread (30-min TTL, auto-cleanup)
- [ ] **SANDBOX-03**: stdout/stderr stream to frontend via SSE events (`code_stdout`, `code_stderr`) in real-time
- [ ] **SANDBOX-04**: Files generated in `/sandbox/output/` are uploaded to Supabase Storage and returned as signed URLs
- [ ] **SANDBOX-05**: `execute_code` tool is only registered when `SANDBOX_ENABLED=true`
- [ ] **SANDBOX-06**: All executions logged in `code_executions` table (code, stdout, stderr, exit code, timing, status)
- [ ] **SANDBOX-07**: Chat shows inline Code Execution Panel with code preview, streaming output, and file downloads
- [ ] **SANDBOX-08**: Custom Docker image pre-installs common packages (python-pptx, pandas, matplotlib, jinja2, requests, beautifulsoup4, etc.)

### Skills Open Standard (EXPORT-*)

- [ ] **EXPORT-01**: User can export a skill as a `.zip` file in agentskills.io-compatible format (SKILL.md frontmatter + instructions + categorized subdirs: scripts/, references/, assets/)
- [ ] **EXPORT-02**: User can import skills from a `.zip` file (max 50MB), supporting single-skill and bulk-import ZIP formats
- [ ] **EXPORT-03**: Import validates name/description and reports per-skill errors without blocking other skills in a bulk import

### Persistent Tool Memory (MEM-*)

- [ ] **MEM-01**: After each tool execution, full result string is stored in `messages.tool_calls` JSONB alongside existing name/arguments/status/summary fields
- [ ] **MEM-02**: Conversation history load reconstructs tool call messages in LLM-expected format (assistant tool-call → tool result → assistant text)
- [ ] **MEM-03**: LLM can reference data from earlier tool calls (UUIDs, search results, file listings) in follow-up questions without re-executing tools

---

## Future Requirements

Items from PRD that are deferred to a later milestone:

- **SKILL-ANALYTICS**: Usage analytics per skill (how often invoked, by whom, success rate)
- **SKILL-VERSIONING**: Skill version history with rollback support
- **SANDBOX-GPU**: GPU-accelerated sandboxed execution for ML workloads
- **SANDBOX-NETWORK**: Controlled network access within sandbox for web scraping beyond beautifulsoup4
- **SFILE-BINARY-PREVIEW**: Rich preview for binary files (PDF render, image thumbnail)
- **EXPORT-MARKETPLACE**: Browse and install community skills from a public registry

---

## Out of Scope (v1.1)

- **Scheduled skill execution** — Skills are invoked by user chat, not by cron or webhook. Reason: agent-initiated actions without user oversight raise auditability concerns for a legal platform.
- **Skill access control beyond private/global** — No per-team or role-based skill visibility. Reason: two-tier model (private/global) matches existing patterns (`is_global` flag); per-team ACL adds schema complexity.
- **Sandbox multi-language support** — Python only. Reason: covers 95%+ of legal-document and data-processing use cases; JS/R sandbox would require separate images.
- **Real-time collaborative skill editing** — Reason: no concurrent editing pattern exists anywhere in LexCore.

---

## Traceability

_Populated by roadmapper after roadmap creation._

| REQ-ID | Phase | Status |
|--------|-------|--------|
| SKILL-01..11 | — | Pending |
| SFILE-01..05 | — | Pending |
| SANDBOX-01..08 | — | Pending |
| EXPORT-01..03 | — | Pending |
| MEM-01..03 | — | Pending |

---

*Created: 2026-04-29 — Milestone v1.1 requirements defined via `/gsd-new-milestone`*
