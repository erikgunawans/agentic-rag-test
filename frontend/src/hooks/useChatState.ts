import { useCallback, useEffect, useRef, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { apiFetch, fetchThreadTodos } from '@/lib/api'
import { buildChildrenMap, getActivePath } from '@/lib/messageTree'
import type { Thread, Message, SSEEvent, ToolStartEvent, ToolResultEvent, Todo } from '@/lib/database.types'

// Phase 18 / WS-07 / WS-08 / WS-11: workspace virtual filesystem types.
// Reflects the shape returned by GET /threads/{id}/files and the
// workspace_updated SSE event payload (plan 18-04 / 18-06).
export type WorkspaceFile = {
  file_path: string
  size_bytes: number
  source: 'agent' | 'sandbox' | 'upload'
  mime_type: string | null
  updated_at: string
}

// Phase 19 / D-24: agent run status chip state.
export type AgentStatus = 'working' | 'waiting_for_user' | 'complete' | 'error' | null

// Phase 20 / PANEL-01 / PANEL-04: harness run slice shape (W10 full type safety).
// Declared here so PlanPanel.tsx (Plan 20-08) can read it without `as any`.
// Plan 20-09 owns the reducer arms, thread-switch reset, and SSE wiring.
export type HarnessRunSlice = null | {
  id: string
  harnessType: string
  status: 'pending' | 'running' | 'paused' | 'completed' | 'cancelled' | 'failed'
  currentPhase: number
  phaseCount: number
  phaseName: string
  errorDetail: string | null
}

/**
 * Phase 21 / Plan 21-05 / D-09 / BATCH-04 / BATCH-06:
 * per-item progress tracking for `llm_batch_agents` phases.
 * Driven by harness_batch_item_start / harness_batch_item_complete SSE events;
 * cleared when harness_phase_complete fires (batch phase finished) or on thread switch.
 *
 * WARNING-6 fix: the reducer's `completed: prev?.completed ?? 0` arm preserves
 * the existing counter when a duplicate batch_item_start is replayed during
 * HIL/cancel resume — see useChatState.batchProgress.test.ts (Test 5).
 */
export type BatchProgressSlice = null | {
  completed: number
  total: number
}

// Phase 20 / Plan 20-10 / UPL-04: in-flight upload tracking for FileUploadButton.
// One entry per in-progress upload; removed on success, error, or abort.
export type UploadingFile = {
  id: string                // client-generated uuid
  filename: string
  sizeBytes: number
  percent: number           // 0..100 (fetch() has no upload progress; stays 0 in v1.3)
  abort: AbortController
  error?: string            // populated on failure
}

// Phase 19 / D-24: sub-agent task types for TaskPanel.
export type TaskToolCall = {
  toolCallId: string
  tool: string
  input?: Record<string, unknown>
  output?: Record<string, unknown> | string
}

export type TaskState = {
  taskId: string
  description: string
  contextFiles: string[]
  toolCalls: TaskToolCall[]
  status: 'running' | 'complete' | 'error'
  result?: string
  error?: { error: string; code: string; detail?: string }
}

// Phase 20 / Plan 20-09: harness status sets — module-level constants so the
// terminal-fade useEffect doesn't need them in its dependency array.
const ACTIVE_HARNESS_STATUSES = new Set<string>(['pending', 'running', 'paused'])
const TERMINAL_HARNESS_STATUSES = new Set<string>(['completed', 'cancelled', 'failed'])
// Suppress "declared but never read" for ACTIVE_HARNESS_STATUSES — kept for
// documentation and future use by HarnessBanner / PlanPanel.
void ACTIVE_HARNESS_STATUSES

export function useChatState() {
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const [allMessages, setAllMessages] = useState<Message[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [branchSelections, setBranchSelections] = useState<Map<string, string>>(new Map())
  const branchSelectionsRef = useRef(branchSelections)
  branchSelectionsRef.current = branchSelections
  const [forkParentId, setForkParentId] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [activeTools, setActiveTools] = useState<ToolStartEvent[]>([])
  const [toolResults, setToolResults] = useState<ToolResultEvent[]>([])
  // Phase 11 SANDBOX-07 D-P11-02: live SSE buffer for execute_code streaming.
  // Keyed by tool_call_id. Cleared on thread switch, send, and post-stream
  // finally — same lifecycle as activeTools/toolResults. After the post-stream
  // refetch the panel switches to reading from the persisted
  // msg.tool_calls.calls[N].output, so the buffer is reset to free memory.
  const [sandboxStreams, setSandboxStreams] = useState<
    Map<string, { stdout: string[]; stderr: string[] }>
  >(new Map())
  // Phase 12 / CTX-01..05 / D-P12-08: per-thread token-usage state for the
  // ContextWindowBar. Backend emits {type:'usage'} exactly once per exchange
  // before terminal done. Reset to null on thread switch (D-P12-09 ensures
  // the bar disappears until the next exchange in the new thread).
  const [usage, setUsage] = useState<{
    prompt: number | null
    completion: number | null
    total: number | null
  } | null>(null)
  const [activeAgent, setActiveAgent] = useState<{ agent: string; display_name: string } | null>(null)
  // Phase 5 D-88 + D-94: redaction status spinner state.
  // Set on backend redaction_status events; null when redaction is OFF or between turns.
  const [redactionStage, setRedactionStage] = useState<
    'anonymizing' | 'deanonymizing' | 'blocked' | null
  >(null)
  const [loadingThreads, setLoadingThreads] = useState(false)
  // ADR-0008: per-thread sticky web-search toggle; resets on thread switch
  const [webSearchEnabled, setWebSearchEnabled] = useState(false)
  // Phase 17 / TODO-06 / D-26: per-thread agent planning todos.
  // Populated from todos_updated SSE events (live) and fetchThreadTodos (reload).
  // Full-replacement semantic (D-06): TODOS_UPDATED replaces the slice in full.
  const [todos, setTodos] = useState<Todo[]>([])
  // Phase 17 / DEEP-01 / D-22: tracks whether the currently-active message
  // (i.e. the most recent send) used deep mode. Used for Plan Panel visibility
  // when todos.length === 0 (e.g. first deep-mode turn before LLM writes todos).
  const [isCurrentMessageDeepMode, setIsCurrentMessageDeepMode] = useState(false)
  // Phase 18 / WS-07 / WS-11: per-thread workspace file list.
  // Populated from GET /threads/{id}/files on thread switch (initial hydration)
  // and kept up-to-date in real time via workspace_updated SSE events.
  // WorkspacePanel is visible whenever workspaceFiles.length > 0 (WS-11),
  // decoupled from Deep Mode.
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFile[]>([])
  // Phase 19 / D-24: Header chip status — tracks current agent run state.
  const [agentStatus, setAgentStatus] = useState<AgentStatus>(null)
  // Phase 19 / D-24: Sub-agent task panel state (Map keyed by task_id).
  const [tasks, setTasks] = useState<Map<string, TaskState>>(new Map())

  // Phase 20 / PANEL-01 / PANEL-04: harness run slice (W10 full type safety).
  // Populated from harness_phase_* SSE events and GET /threads/{id}/harness/active.
  // Plan 20-09 owns the reducer arms, thread-switch reset, and SSE wiring.
  const [harnessRun, setHarnessRun] = useState<HarnessRunSlice>(null)

  // Phase 21 / Plan 21-05 / D-09 / BATCH-04 / BATCH-06: per-item batch progress.
  // Seeded by harness_batch_item_start, incremented by harness_batch_item_complete,
  // cleared by harness_phase_complete and on thread switch.
  const [batchProgress, setBatchProgress] = useState<BatchProgressSlice>(null)

  // Phase 20 / Plan 20-10 / UPL-04: in-flight upload state.
  // Keyed by client-generated uuid. Cleaned up on success, error, or abort.
  // Thread switch aborts all in-flight uploads and resets to empty Map.
  const [uploadingFiles, setUploadingFiles] = useState<Map<string, UploadingFile>>(new Map())

  // Phase 20 / Plan 20-09 / D-02: reject-while-active toast state.
  // Set when the backend returns 409 {error: 'harness_in_progress'} during a chat send.
  // Consumed by the UI (HarnessBanner or a toast renderer) and cleared on next send.
  const [harnessToast, setHarnessToast] = useState<{
    message: string
    harnessType: string
    currentPhase: number
    phaseCount: number
  } | null>(null)

  const loadThreads = useCallback(async () => {
    setLoadingThreads(true)
    try {
      const res = await apiFetch('/threads')
      const data: Thread[] = await res.json()
      setThreads(data)
    } finally {
      setLoadingThreads(false)
    }
  }, [])

  useEffect(() => {
    loadThreads()
  }, [loadThreads])

  useEffect(() => {
    setWebSearchEnabled(false) // ADR-0008: per-thread sticky; reset on thread switch
  }, [activeThreadId])

  // Phase 17 / TODO-07 / D-21: hydrate todos on thread switch.
  // Reset to [] immediately (T-17-16: prevent stale cross-thread todos from showing),
  // then fetch current todos from GET /threads/{id}/todos.
  // isCurrentMessageDeepMode also resets so the panel hides until the user
  // sends a deep-mode message or there are persisted todos.
  useEffect(() => {
    setTodos([])
    setIsCurrentMessageDeepMode(false)
    if (!activeThreadId) return

    supabase.auth.getSession().then(({ data }) => {
      const token = data.session?.access_token
      if (!token || !activeThreadId) return
      fetchThreadTodos(activeThreadId, token)
        .then(({ todos: fetched }) => {
          // Guard against stale responses if user switched thread again quickly
          setTodos(fetched)
        })
        .catch(() => {
          // Non-blocking: leave todos as [] if fetch fails
        })
    })
  }, [activeThreadId])

  // Phase 18 / WS-07 / WS-11: hydrate workspace files on thread switch.
  // Immediately resets to [] (prevents stale files from a previous thread
  // appearing briefly while the new fetch is in flight).
  useEffect(() => {
    setWorkspaceFiles([])
    if (!activeThreadId) return

    apiFetch(`/threads/${activeThreadId}/files`)
      .then((r) => r.json() as Promise<WorkspaceFile[]>)
      .then((data) => setWorkspaceFiles(data ?? []))
      .catch(() => setWorkspaceFiles([]))
  }, [activeThreadId])

  // Phase 19 / D-24: reset agent status and tasks on thread switch.
  // Prevents stale chip/panel state from a previous thread leaking into the new one.
  useEffect(() => {
    setAgentStatus(null)
    setTasks(new Map())
  }, [activeThreadId])

  // Phase 20 / Plan 20-09 / HARN-09: 3000ms terminal-fade for harnessRun.
  // When harnessRun transitions to a terminal state (completed/cancelled/failed),
  // set to null after 3000ms. Mirrors AgentStatusChip auto-fade pattern (D-24).
  // The single-source-of-truth approach: useChatState owns the timeout, not
  // HarnessBanner, so the slice is null by the time the next render cycle runs.
  useEffect(() => {
    if (harnessRun && TERMINAL_HARNESS_STATUSES.has(harnessRun.status)) {
      const timer = setTimeout(() => setHarnessRun(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [harnessRun]) // TERMINAL_HARNESS_STATUSES is module-scoped constant; safe to omit

  // Phase 20 / Plan 20-10 / UPL-04: abort in-flight uploads on thread switch.
  // AbortController.abort() is idempotent — safe to call even on already-settled uploads.
  useEffect(() => {
    setUploadingFiles((prev) => {
      prev.forEach((u) => u.abort.abort())
      return new Map()
    })
  }, [activeThreadId])

  // Phase 20 / Plan 20-09 / HARN-09: reset harnessRun on thread switch + rehydrate
  // from GET /threads/{id}/harness/active. Prevents stale harness state leaking
  // across threads. The /harness/active endpoint returns the current active run (if
  // any), seeding the banner and locked PlanPanel immediately on reload/thread-switch.
  // W8: gatekeeper_complete SSE already seeds phaseCount, so the rehydration fetch
  // mainly fills harnessType + phaseName that gatekeeper_complete omits.
  useEffect(() => {
    setHarnessRun(null)
    // Phase 21 / Plan 21-05 / D-09: mirror harnessRun reset — clear batch
    // progress on thread switch so a previous thread's "Analyzing clause N/M"
    // suffix doesn't bleed into the new thread's banner.
    setBatchProgress(null)
    if (!activeThreadId) return
    apiFetch(`/chat/threads/${activeThreadId}/harness/active`)
      .then((r) => r.json() as Promise<{ harnessRun: HarnessRunSlice }>)
      .then((data) => {
        if (data.harnessRun) setHarnessRun(data.harnessRun)
      })
      .catch(() => {
        // Non-fatal: leave harnessRun as null if /harness/active fetch fails.
        // Backend may not have this endpoint until Plan 20-04 is applied.
      })
  }, [activeThreadId])

  function rebuildVisibleMessages(all: Message[], selections: Map<string, string>) {
    const childrenMap = buildChildrenMap(all)
    setMessages(getActivePath(childrenMap, selections))
  }

  async function handleSelectThread(threadId: string) {
    setActiveThreadId(threadId)
    setStreamingContent('')
    setRedactionStage(null)
    // Phase 11 SANDBOX-07 D-P11-02: thread switch clears live execute_code
    // buffers (T-11-05-1 — prevent stale Map entries leaking across threads).
    setSandboxStreams(new Map())
    // Phase 12 D-P12-08 / D-P12-09: reset usage on thread switch so the
    // ContextWindowBar disappears until the next exchange in the new thread.
    setUsage(null)
    setForkParentId(null)
    const newSelections = new Map<string, string>()
    setBranchSelections(newSelections)

    const { data } = await supabase
      .from('messages')
      .select('*')
      .eq('thread_id', threadId)
      .order('created_at', { ascending: true })

    const all = (data as Message[]) ?? []
    setAllMessages(all)
    rebuildVisibleMessages(all, newSelections)
  }

  async function handleCreateThread() {
    const res = await apiFetch('/threads', {
      method: 'POST',
      body: JSON.stringify({ title: 'New Thread' }),
    })
    const thread: Thread = await res.json()
    setThreads((prev) => [thread, ...prev])
    setActiveThreadId(thread.id)
    setAllMessages([])
    setMessages([])
    setBranchSelections(new Map())
    setForkParentId(null)
    setStreamingContent('')
    setRedactionStage(null)
    return thread
  }

  async function handleDeleteThread(threadId: string) {
    await apiFetch(`/threads/${threadId}`, { method: 'DELETE' })
    setThreads((prev) => prev.filter((t) => t.id !== threadId))
    if (activeThreadId === threadId) {
      setActiveThreadId(null)
      setAllMessages([])
      setMessages([])
    }
  }

  function handleSwitchBranch(forkPointId: string, selectedChildId: string) {
    const newSelections = new Map(branchSelections)
    newSelections.set(forkPointId, selectedChildId)
    setBranchSelections(newSelections)
    rebuildVisibleMessages(allMessages, newSelections)
  }

  function handleForkAt(messageId: string) {
    setForkParentId(messageId)
  }

  function handleCancelFork() {
    setForkParentId(null)
  }

  async function sendMessageToThread(
    threadId: string,
    content: string,
    // Phase 17 / DEEP-01 / D-24 / D-26: per-message deep mode flag.
    // Forwarded to POST /chat/stream when true (DEEP-03: omitted when false to
    // preserve byte-identical legacy payload).
    opts?: { deepMode?: boolean }
  ) {
    // Determine parent: if forking, use forkParentId; otherwise use the last visible message
    const parentId = forkParentId ?? messages[messages.length - 1]?.id ?? null

    const optimisticMsg: Message = {
      id: `optimistic-${Date.now()}`,
      thread_id: threadId,
      user_id: '',
      role: 'user',
      content,
      parent_message_id: parentId,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, optimisticMsg])
    setIsStreaming(true)
    setStreamingContent('')
    setActiveTools([])
    setToolResults([])
    setActiveAgent(null)
    setRedactionStage(null)
    // Phase 17 / D-22: track deep mode for current turn (panel visibility rule).
    setIsCurrentMessageDeepMode(opts?.deepMode === true)
    // Phase 11 SANDBOX-07 D-P11-02: fresh send starts with an empty buffer;
    // mirrors activeTools/toolResults reset at the same lifecycle site.
    setSandboxStreams(new Map())
    // Phase 12 D-P12-08: clear stale usage at the start of a new exchange so
    // the bar reflects only this turn's tokens. SSE 'usage' event re-populates.
    setUsage(null)
    setForkParentId(null)
    // Phase 19 / D-24: clear agent status and tasks at send-start so prior
    // turn's chip/panel don't leak into the new exchange.
    setAgentStatus(null)
    setTasks(new Map())

    try {
      // Phase 17 / DEEP-01 / DEEP-03: only include deep_mode in payload when true.
      // Byte-identical legacy payload when toggle is off (omit the key entirely).
      const requestBody: Record<string, unknown> = {
        thread_id: threadId,
        message: content,
        parent_message_id: parentId,
        web_search: webSearchEnabled, // ADR-0008
      }
      if (opts?.deepMode) {
        requestBody.deep_mode = true
      }

      let response: Response
      try {
        response = await apiFetch('/chat/stream', {
          method: 'POST',
          body: JSON.stringify(requestBody),
        })
      } catch (fetchErr) {
        // Phase 20 / Plan 20-09 / D-02: reject-while-active 409 handler.
        // When the backend returns 409 {error: 'harness_in_progress', ...},
        // surface a toast with the running harness info and preserve the message draft.
        // apiFetch now attaches .status and .body to thrown errors.
        const err = fetchErr as Error & { status?: number; body?: Record<string, unknown> }
        if (
          err.status === 409 &&
          err.body &&
          err.body.error === 'harness_in_progress'
        ) {
          const toastBody = err.body as {
            error: string
            harness_type?: string
            current_phase?: number
            phase_count?: number
            phase_name?: string
          }
          setHarnessToast({
            message: `${toastBody.harness_type ?? 'Harness'} running (phase ${toastBody.current_phase ?? 0}/${toastBody.phase_count ?? harnessRun?.phaseCount ?? 1}) — please wait`,
            harnessType: toastBody.harness_type ?? '',
            currentPhase: toastBody.current_phase ?? 0,
            phaseCount: toastBody.phase_count ?? harnessRun?.phaseCount ?? 1,
          })
          // Remove the optimistic user message (it never reached the server).
          setMessages((prev) => prev.filter((m) => !m.id.startsWith('optimistic-')))
          // NOTE: do NOT clear the message draft — user should be able to retry.
          return
        }
        throw fetchErr
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let assistantContent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          let event: SSEEvent
          try {
            event = JSON.parse(line.slice(6)) as SSEEvent
          } catch {
            continue
          }

          if (event.type === 'thread_title') {
            setThreads((prev) =>
              prev.map((t) =>
                t.id === event.thread_id ? { ...t, title: event.title } : t
              )
            )
          } else if (event.type === 'agent_start') {
            setActiveAgent({ agent: event.agent, display_name: event.display_name })
          } else if (event.type === 'agent_done') {
            setActiveAgent(null)
          } else if (event.type === 'tool_start') {
            // Phase 19 / D-06: polymorphic — when task_id present, route to tasks slice;
            // otherwise fall through to existing setActiveTools path.
            if ('task_id' in event && event.task_id) {
              setTasks((prev) => {
                const next = new Map(prev)
                const t = next.get(event.task_id!)
                if (t) next.set(event.task_id!, { ...t, toolCalls: [...t.toolCalls, { toolCallId: event.tool_call_id ?? '', tool: event.tool, input: event.input }] })
                return next
              })
            } else {
              setActiveTools((prev) => [...prev, event])
            }
          } else if (event.type === 'tool_result') {
            // Phase 19 / D-06: polymorphic — when task_id present, route to tasks slice;
            // otherwise fall through to existing setToolResults path.
            if ('task_id' in event && event.task_id) {
              // tool_result with task_id — currently no per-tool-call output update needed
              // (task_complete carries the final result). No-op for tasks slice here.
            } else {
              setActiveTools((prev) => {
                const idx = prev.findIndex((t) => t.tool === event.tool)
                if (idx >= 0) return [...prev.slice(0, idx), ...prev.slice(idx + 1)]
                return prev
              })
              setToolResults((prev) => [...prev, event])
            }
          } else if (event.type === 'redaction_status') {
            // Phase 5 D-88: status spinner state during the buffer window.
            setRedactionStage(event.stage)
            if (event.stage === 'blocked') {
              // D-94 egress trip — partial text is invalid; clear it.
              setStreamingContent('')
              assistantContent = ''
            }
          } else if (event.type === 'code_stdout') {
            // Phase 11 SANDBOX-07 D-P11-02: append stdout line to per-call buffer.
            // Immutable Map update mirrors setActiveTools((prev) => [...prev, event]).
            setSandboxStreams((prev) => {
              const next = new Map(prev)
              const cur = next.get(event.tool_call_id) ?? { stdout: [], stderr: [] }
              next.set(event.tool_call_id, {
                stdout: [...cur.stdout, event.line],
                stderr: cur.stderr,
              })
              return next
            })
          } else if (event.type === 'code_stderr') {
            // Phase 11 SANDBOX-07 D-P11-02: append stderr line to per-call buffer.
            setSandboxStreams((prev) => {
              const next = new Map(prev)
              const cur = next.get(event.tool_call_id) ?? { stdout: [], stderr: [] }
              next.set(event.tool_call_id, {
                stdout: cur.stdout,
                stderr: [...cur.stderr, event.line],
              })
              return next
            })
          } else if (event.type === 'usage') {
            // Phase 12 CTX-02 / D-P12-01: backend emits this exactly once per
            // exchange, immediately before terminal done. Some providers send
            // partial values (None for completion); store as-is and let the
            // ContextWindowBar component decide how to render partial state.
            setUsage({
              prompt: event.prompt_tokens,
              completion: event.completion_tokens,
              total: event.total_tokens,
            })
          } else if (event.type === 'todos_updated') {
            // Phase 17 / TODO-03 / D-17: full-replacement update of the per-thread
            // todo list. Fired after every write_todos or read_todos LLM tool call
            // (D-18: fires AFTER DB write commits, BEFORE tool_result).
            setTodos(event.todos)
          } else if (event.type === 'workspace_updated') {
            // Phase 18 / WS-07 / WS-08: real-time workspace file list updates.
            // operation: 'create' | 'update' — prepend / move-to-top.
            // operation: 'delete' — remove from list.
            // Keyed by file_path (unique per thread).
            const { file_path, operation, size_bytes, source } = event
            setWorkspaceFiles((prev) => {
              const idx = prev.findIndex((f) => f.file_path === file_path)
              if (operation === 'delete') {
                return prev.filter((f) => f.file_path !== file_path)
              }
              const newEntry: WorkspaceFile = {
                file_path,
                size_bytes,
                source,
                mime_type: null, // server didn't send; refreshed on next list fetch
                updated_at: new Date().toISOString(),
              }
              if (idx === -1) {
                // create — prepend (most recent first)
                return [newEntry, ...prev]
              }
              // update — replace in place and move to top
              const next = [...prev]
              next.splice(idx, 1)
              return [newEntry, ...next]
            })
          } else if (event.type === 'agent_status') {
            // Phase 19 / STATUS-01 / D-24: update agent run status chip.
            setAgentStatus(event.status)
          } else if (event.type === 'task_start') {
            // Phase 19 / TASK-07 / D-25: new sub-agent task card.
            setTasks((prev) => {
              const next = new Map(prev)
              const newTask: TaskState = {
                taskId: event.task_id,
                description: event.description,
                contextFiles: event.context_files ?? [],
                toolCalls: [],
                status: 'running',
              }
              next.set(event.task_id, newTask)
              return next
            })
          } else if (event.type === 'task_complete') {
            // Phase 19 / TASK-07 / D-25: task completed — update card to complete.
            setTasks((prev) => {
              const next = new Map(prev)
              const t = next.get(event.task_id)
              if (t) next.set(event.task_id, { ...t, status: 'complete', result: event.result })
              return next
            })
          } else if (event.type === 'task_error') {
            // Phase 19 / TASK-07 / D-25: task failed — update card to error state.
            setTasks((prev) => {
              const next = new Map(prev)
              const t = next.get(event.task_id)
              if (t) next.set(event.task_id, { ...t, status: 'error', error: { error: event.error, code: event.code, detail: event.detail } })
              return next
            })
          } else if (event.type === 'harness_phase_start') {
            // Phase 20 / Plan 20-09 / HARN-09: harness phase started.
            // Sets status='running', updates currentPhase and phaseName.
            // phaseCount is typically already seeded by gatekeeper_complete (W8).
            setHarnessRun((prev) => ({
              id: event.harness_run_id as string,
              harnessType: (prev?.harnessType) ?? '',
              status: 'running',
              currentPhase: event.phase_index as number,
              phaseCount: (prev?.phaseCount) ?? 0,
              phaseName: event.phase_name as string,
              errorDetail: null,
            }))
          } else if (event.type === 'harness_batch_item_start') {
            // Phase 21 / Plan 21-05 / D-09 / BATCH-04: batch sub-agent started for an item.
            // Seed total from event.items_total. WARNING-6 fix: preserve any
            // existing `completed` counter so a resume-replayed batch_item_start
            // does not reset progress to 0.
            setBatchProgress((prev) => ({
              completed: prev?.completed ?? 0,
              total:
                ((event as unknown as { items_total?: number }).items_total) ??
                prev?.total ??
                0,
            }))
          } else if (event.type === 'harness_batch_item_complete') {
            // Phase 21 / Plan 21-05 / D-09 / BATCH-06: batch sub-agent finished an item.
            // Increment completed; if no prior start was seen (defensive), seed total from event.
            setBatchProgress((prev) =>
              prev
                ? { ...prev, completed: prev.completed + 1 }
                : {
                    completed: 1,
                    total:
                      ((event as unknown as { items_total?: number }).items_total) ?? 1,
                  }
            )
          } else if (event.type === 'harness_phase_complete') {
            // Phase 20 / Plan 20-09 / HARN-09: harness phase completed.
            // Bumps currentPhase by 1.
            setHarnessRun((prev) => prev ? { ...prev, currentPhase: prev.currentPhase + 1 } : prev)
            // Phase 21 / Plan 21-05 / D-09: clear batch progress at phase boundary.
            setBatchProgress(null)
          } else if (event.type === 'harness_phase_error') {
            // Phase 20 / Plan 20-09 / HARN-09: harness phase errored.
            // code='cancelled' or reason='cancelled_by_user' → cancelled; else → failed.
            const isCancelled =
              event.code === 'cancelled' || event.reason === 'cancelled_by_user'
            setHarnessRun((prev) =>
              prev
                ? {
                    ...prev,
                    status: isCancelled ? 'cancelled' : 'failed',
                    errorDetail: isCancelled ? null : ((event.detail as string) ?? null),
                  }
                : prev
            )
          } else if (event.type === 'harness_complete') {
            // Phase 20 / Plan 20-09 / HARN-09: harness run finished.
            // status from payload: 'completed' | 'failed' | 'cancelled'.
            const terminalStatus = (event.status as HarnessRunSlice extends infer T
              ? T extends { status: infer S }
                ? S
                : never
              : never) ?? 'completed'
            setHarnessRun((prev) =>
              prev ? { ...prev, status: terminalStatus } : prev
            )
          } else if (
            event.type === 'gatekeeper_complete' &&
            event.triggered &&
            event.harness_run_id
          ) {
            // Phase 20 / Plan 20-09 / W8 fix: gatekeeper fired the harness sentinel.
            // Seed harnessRun immediately from event payload so the banner shows
            // "phase 1 of N" fraction on the very first harness_phase_start tick,
            // without waiting for a separate /harness/active fetch.
            // Plan 20-04 added phase_count to this payload specifically for this fix.
            const runId = event.harness_run_id as string
            const phaseCount =
              typeof event.phase_count === 'number' ? event.phase_count : 0
            setHarnessRun({
              id: runId,
              harnessType: '',
              status: 'pending',
              currentPhase: 0,
              phaseCount,
              phaseName: '',
              errorDetail: null,
            })
            // Follow-up fetch to fill harnessType + phaseName (not in gatekeeper_complete
            // payload — would bloat it). Non-blocking; if it fails, the banner still shows.
            if (activeThreadId) {
              apiFetch(`/chat/threads/${activeThreadId}/harness/active`)
                .then((r) => r.json() as Promise<{ harnessRun: HarnessRunSlice }>)
                .then((data) => {
                  if (data.harnessRun) setHarnessRun(data.harnessRun)
                })
                .catch(() => {
                  /* non-fatal */
                })
            }
          } else if (
            event.type === 'harness_sub_agent_start' ||
            event.type === 'harness_sub_agent_complete'
          ) {
            // Phase 20 / Plan 20-09 / B1 forward-compat: harness engine emits sub-agent
            // telemetry events around llm_agent phase dispatch. v1.3 has no UI surface
            // for sub-agent telemetry inside the harness. Explicit no-op arm prevents
            // these events from falling through to the delta/done branch and producing
            // spurious console warnings. Phase 21 will hook in here.
          } else {
            // CR-21-05 (UAT finding): the gatekeeper emits delta events as
            // {type: 'delta', content: '...'} (per gatekeeper.py SSE shape) while
            // the agent path emits {type: 'delta', delta: '...'}. Accept both so
            // gatekeeper greetings aren't silently dropped before the harness
            // triggers — without this fallback the user sees an empty bubble.
            const delta =
              'delta' in event
                ? (event as { delta?: string }).delta
                : 'content' in event
                  ? (event as { content?: string }).content
                  : ''
            const isDone = 'done' in event ? event.done : false
            if (!isDone && delta) {
              assistantContent += delta
              setStreamingContent(assistantContent)
            }
          }
        }
      }

      // Refetch all messages and rebuild tree
      const { data } = await supabase
        .from('messages')
        .select('*')
        .eq('thread_id', threadId)
        .order('created_at', { ascending: true })

      const all = (data as Message[]) ?? []
      setAllMessages(all)
      rebuildVisibleMessages(all, branchSelectionsRef.current)
      loadThreads()
    } finally {
      setIsStreaming(false)
      setStreamingContent('')
      setActiveTools([])
      setToolResults([])
      setActiveAgent(null)
      // Phase 11 SANDBOX-07 D-P11-02: clear live buffer; CodeExecutionPanel
      // (Plan 11-06) now reads persisted output from msg.tool_calls.calls[N].
      setSandboxStreams(new Map())
      // D-94: keep `redactionStage === 'blocked'` visible after the stream ends so
      // the user sees the explanation card. It is reset on the next handleSendMessage.
      setRedactionStage((prev) => (prev === 'blocked' ? 'blocked' : null))
    }
  }

  // Phase 20 / Plan 20-10 / UPL-04: uploadingFiles helper functions.
  // FileUploadButton calls these to manage in-flight upload state.
  function startUpload(meta: { id: string; filename: string; sizeBytes: number; abort: AbortController }) {
    setUploadingFiles((prev) => {
      const m = new Map(prev)
      m.set(meta.id, { ...meta, percent: 0 })
      return m
    })
  }

  function updateUploadProgress(id: string, percent: number) {
    setUploadingFiles((prev) => {
      const m = new Map(prev)
      const entry = m.get(id)
      if (entry) m.set(id, { ...entry, percent })
      return m
    })
  }

  function completeUpload(id: string) {
    setUploadingFiles((prev) => {
      const m = new Map(prev)
      m.delete(id)
      return m
    })
  }

  function failUpload(id: string, error: string) {
    setUploadingFiles((prev) => {
      const m = new Map(prev)
      const entry = m.get(id)
      if (entry) m.set(id, { ...entry, error })
      return m
    })
  }

  async function handleSendMessage(content: string, opts?: { deepMode?: boolean }) {
    if (!activeThreadId || isStreaming) return
    await sendMessageToThread(activeThreadId, content, opts)
  }

  function handleNewChat() {
    setActiveThreadId(null)
    setAllMessages([])
    setMessages([])
    setBranchSelections(new Map())
    setForkParentId(null)
    setStreamingContent('')
    setRedactionStage(null)
    // Phase 12 D-P12-08: clear usage on new-chat (no thread is active).
    setUsage(null)
    // Phase 18 / WS-11: clear workspace files when no thread is active.
    setWorkspaceFiles([])
  }

  async function handleSendFirstMessage(content: string, opts?: { deepMode?: boolean }) {
    if (isStreaming) return
    const thread = await handleCreateThread()
    await sendMessageToThread(thread.id, content, opts)
  }

  return {
    threads,
    activeThreadId,
    allMessages,
    messages,
    forkParentId,
    isStreaming,
    streamingContent,
    activeTools,
    toolResults,
    activeAgent,
    redactionStage,
    sandboxStreams, // Phase 11 SANDBOX-07 D-P11-02
    usage,          // Phase 12 / CTX-01..05
    loadingThreads,
    webSearchEnabled,
    setWebSearchEnabled,
    todos,                       // Phase 17 / TODO-06 / D-26
    isCurrentMessageDeepMode,    // Phase 17 / D-22
    workspaceFiles,              // Phase 18 / WS-07 / WS-11
    agentStatus,                 // Phase 19 / D-24
    setAgentStatus,              // Phase 19 — used by AgentStatusChip auto-fade effect
    tasks,                       // Phase 19 / D-24
    harnessRun,                  // Phase 20 / PANEL-04 — read by PlanPanel locked variant
    setHarnessRun,               // Phase 20 — Plan 20-09 wires SSE reducer arms
    batchProgress,               // Phase 21 / Plan 21-05 / D-09 — read by HarnessBanner suffix
    setBatchProgress,            // Phase 21 — exposed for tests / future direct seeders
    harnessToast,                // Phase 20 / Plan 20-09 / D-02 — 409 reject-while-active toast
    setHarnessToast,             // Phase 20 — lets HarnessBanner clear toast after display
    uploadingFiles,              // Phase 20 / Plan 20-10 / UPL-04 — in-flight upload tracking
    startUpload,                 // Phase 20 / Plan 20-10 — add entry to uploadingFiles Map
    updateUploadProgress,        // Phase 20 / Plan 20-10 — update percent for in-flight upload
    completeUpload,              // Phase 20 / Plan 20-10 — remove completed upload from Map
    failUpload,                  // Phase 20 / Plan 20-10 — mark upload as failed with error msg
    handleSelectThread,
    handleCreateThread,
    handleDeleteThread,
    handleSendMessage,
    handleNewChat,
    handleSendFirstMessage,
    handleSwitchBranch,
    handleForkAt,
    handleCancelFork,
  }
}
