---
phase: 17-deep-mode-foundation-planning-todos-plan-panel
plan: 07
type: execute
wave: 4
depends_on: [04, 05, 06]
files_modified:
  - frontend/src/components/chat/PlanPanel.tsx
  - frontend/src/hooks/useChatState.tsx
  - frontend/src/components/layout/AppLayout.tsx
  - frontend/src/lib/api.ts
  - frontend/src/types/index.ts
  - frontend/src/i18n/en.json
  - frontend/src/i18n/id.json
  - frontend/src/components/chat/__tests__/PlanPanel.test.tsx
autonomous: true
requirements: [TODO-06, TODO-07]
must_haves:
  truths:
    - "frontend/src/components/chat/PlanPanel.tsx is a NEW component that renders the per-thread agent_todos list as a sidebar panel."
    - "PlanPanel reads live state from chat-state TODOS_UPDATED action (driven by todos_updated SSE event); on thread reload it hydrates from GET /threads/{id}/todos."
    - "PlanPanel visibility rule (D-22): visible whenever (a) the current message is deep_mode OR (b) the thread has any agent_todos rows on reload; hidden otherwise."
    - "PlanPanel displays each todo with status indicator (D-25): pending = zinc dot, in_progress = pulsing purple dot, completed = green check (lucide-react icons; no new design tokens)."
    - "PlanPanel is collapsible using existing useSidebar pattern (matches SubAgentPanel + CodeExecutionPanel)."
    - "PlanPanel is a persistent sidebar — NO backdrop-blur / glass (CLAUDE.md panel rule); solid panel surface only."
    - "useChatState reducer accepts a TODOS_UPDATED action that replaces the todos slice; SSE event dispatches this action."
    - "lib/api.ts has fetchThreadTodos(thread_id, token) calling GET /threads/{id}/todos and returning {todos: ...}; called once on thread mount/reload."
    - "Reducer accumulates todos for the current thread; when navigating to a different thread, todos are reset and re-hydrated."
    - "PlanPanel renders correctly across the live → reload cycle: a thread that ran in deep mode shows the same panel state after page refresh (TODO-07)."
    - "Vitest tests assert: panel hidden when no todos and no deep mode, panel visible with todos, status indicators map to correct visual, hydration on mount calls fetchThreadTodos, TODOS_UPDATED action mutates state."
    - "i18n strings in id.json and en.json: 'planPanel.title', 'planPanel.empty', status labels."
  artifacts:
    - path: "frontend/src/components/chat/PlanPanel.tsx"
      provides: "NEW Plan Panel sidebar component."
      contains: "PlanPanel"
    - path: "frontend/src/hooks/useChatState.tsx"
      provides: "TODOS_UPDATED action + todos slice + thread-mount hydration trigger."
      contains: "TODOS_UPDATED"
    - path: "frontend/src/components/layout/AppLayout.tsx"
      provides: "Slot the PlanPanel into the existing sidebar (alongside SubAgentPanel + CodeExecutionPanel)."
      contains: "PlanPanel"
    - path: "frontend/src/lib/api.ts"
      provides: "fetchThreadTodos function consuming GET /threads/{id}/todos."
      contains: "fetchThreadTodos"
    - path: "frontend/src/types/index.ts"
      provides: "Todo TypeScript type matching backend payload {id, content, status, position}."
      contains: "type Todo"
    - path: "frontend/src/components/chat/__tests__/PlanPanel.test.tsx"
      provides: "Vitest tests for PlanPanel visibility, status indicators, hydration, SSE-driven state updates."
      contains: "test_panel_hydrates"
  key_links:
    - from: "frontend/src/components/chat/PlanPanel.tsx"
      to: "frontend/src/hooks/useChatState.tsx"
      via: "consumes todos slice"
      pattern: "todos"
    - from: "frontend/src/hooks/useChatState.tsx"
      to: "frontend/src/lib/api.ts"
      via: "fetchThreadTodos on thread mount"
      pattern: "fetchThreadTodos"
    - from: "frontend/src/hooks/useChatState.tsx"
      to: "todos_updated SSE event"
      via: "TODOS_UPDATED action dispatch"
      pattern: "todos_updated"
---

<objective>
Capstone of Phase 17 — the Plan Panel UI itself. Real-time SSE-driven todo display + thread-reload hydration. Closes the loop between Plans 17-03/04 (backend writes + SSE), 17-05 (REST hydrate), and 17-06 (Deep Mode toggle + badge).

Per D-20: follows the proven sidebar-panel + history-reconstruction pattern from `SubAgentPanel.tsx` and `CodeExecutionPanel.tsx`.

Per D-21: live state from `todos_updated` SSE → reducer; reload state from `GET /threads/{id}/todos`.

Per D-22: visibility rule — visible whenever current message is deep_mode OR thread has any agent_todos rows on reload (allows panel to survive after a deep run completes).

Per D-25: status indicators (pending zinc dot, in_progress pulsing purple, completed green check) using existing lucide-react icons.

Per D-26: state via existing `useChatState` reducer with new TODOS_UPDATED action.

Wave 4: depends on Plan 17-04 (todos_updated SSE event), Plan 17-05 (GET /todos endpoint), and Plan 17-06 (deep_mode toggle / badge UI infra). Last plan in Phase 17.

Output: NEW PlanPanel component + reducer extension + AppLayout slot + api/types extensions + Vitest tests + i18n.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-CONTEXT.md
@.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-04-deep-mode-chat-loop-branch-PLAN.md
@.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-05-todos-rest-endpoint-PLAN.md
@frontend/src/components/chat/SubAgentPanel.tsx
@frontend/src/components/chat/CodeExecutionPanel.tsx
@frontend/src/hooks/useChatState.tsx
@frontend/src/components/layout/AppLayout.tsx

<interfaces>
**Existing `SubAgentPanel.tsx` and `CodeExecutionPanel.tsx`** — both are sidebar panels that:
- Render a list of items (sub-agent tasks / code executions).
- Are mounted in AppLayout sidebar alongside other persistent panels.
- Handle live SSE updates (state in useChatState reducer).
- Reconstruct history from per-message tool_calls JSONB on thread reload.
- Are collapsible via the existing sidebar collapse pattern (useSidebar hook or local state).
- Use existing 2026 Calibrated Restraint tokens; no glass.

**PlanPanel mirrors that structure** but with simpler data: a single per-thread list of todos (not per-message accumulation).

**Existing `useChatState.tsx`** — reducer pattern with action types like SSE_EVENT, MESSAGE_RECEIVED, etc. We add:
- New action type: `TODOS_UPDATED` carrying `todos: Todo[]`.
- New slice: `todos: Todo[]` (in state).
- Reducer: TODOS_UPDATED replaces the slice in full (full-replacement semantic; matches backend D-06).
- THREAD_LOADED side-effect (or useEffect on thread_id change) calls `fetchThreadTodos(thread_id)` and dispatches TODOS_UPDATED on success.

**SSE event consumption** — existing useChatState SSE event dispatcher needs an arm for `event.type === 'todos_updated'` that dispatches TODOS_UPDATED. Look at how `tool_start` / `tool_result` are handled — replicate.

**Visibility logic (D-22):**
```ts
const showPlanPanel =
  isCurrentMessageDeepMode || todos.length > 0;
```
- `isCurrentMessageDeepMode` = the local toggle from MessageInput AND/OR the deep_mode flag on the most-recent message.
- The "OR todos.length > 0" path covers thread-reload cases where the user navigates to a thread that had a deep run — the panel still shows the saved plan.

**`fetchThreadTodos(thread_id, token)`** — new function in api.ts:
```ts
export async function fetchThreadTodos(thread_id: string, token: string): Promise<{todos: Todo[]}> {
  const res = await fetch(`${API_BASE_URL}/threads/${thread_id}/todos`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(...);
  return res.json();
}
```

**`Todo` type:**
```ts
export type Todo = {
  id: string;
  content: string;
  status: 'pending' | 'in_progress' | 'completed';
  position: number;
};
```

**Status indicator icons (D-25)** — lucide-react existing dep:
- pending: `Circle` (zinc)
- in_progress: `Loader2` with `animate-spin` OR `Circle` with custom pulse keyframe (purple accent)
- completed: `CheckCircle2` (green-500)

**Vitest 3.2** — co-located `__tests__/`. Use `@testing-library/react`. CodeExecutionPanel.test.tsx is the closest analog for sidebar-panel test idioms.
</interfaces>

</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add Todo type, fetchThreadTodos, reducer extension; write failing PlanPanel tests</name>
  <files>frontend/src/types/index.ts, frontend/src/lib/api.ts, frontend/src/hooks/useChatState.tsx, frontend/src/components/chat/__tests__/PlanPanel.test.tsx, frontend/src/i18n/en.json, frontend/src/i18n/id.json</files>
  <action>
    **1. Type:** Add to `frontend/src/types/index.ts`:
    ```ts
    export type TodoStatus = 'pending' | 'in_progress' | 'completed';
    export type Todo = {
      id: string;
      content: string;
      status: TodoStatus;
      position: number;
    };
    ```

    **2. api.ts:** Add `fetchThreadTodos(thread_id: string, token: string)` returning `Promise<{todos: Todo[]}>`. Standard fetch + Authorization Bearer header (replicate existing helpers).

    **3. useChatState.tsx:**
    - Add `todos: Todo[]` slice (default []).
    - Add action type `TODOS_UPDATED` with payload `{todos: Todo[]}`.
    - Reducer: TODOS_UPDATED replaces slice in full.
    - SSE event handler: when incoming event has `type === 'todos_updated'`, dispatch TODOS_UPDATED with event.todos.
    - useEffect on `thread_id` change: call `fetchThreadTodos(thread_id, token)` and dispatch TODOS_UPDATED on success; reset to [] on failure or while loading.

    **4. i18n strings:**
    - id.json: `planPanel.title`: "Rencana", `planPanel.empty`: "Belum ada rencana", `planPanel.status.pending`: "Menunggu", `planPanel.status.inProgress`: "Sedang berjalan", `planPanel.status.completed`: "Selesai".
    - en.json: same keys, English text ("Plan", "No plan yet", "Pending", "In Progress", "Completed").

    **5. Vitest test file** `frontend/src/components/chat/__tests__/PlanPanel.test.tsx` (component does NOT exist yet — RED):
    - test_panel_hidden_when_empty: render with state `{todos: [], isCurrentMessageDeepMode: false}` → no panel in document.
    - test_panel_visible_with_todos: state `{todos: [{...}, {...}]}` → panel renders with "Rencana"/"Plan" title and 2 todo rows.
    - test_panel_visible_with_deep_mode_active_no_todos: `{todos: [], isCurrentMessageDeepMode: true}` → panel renders with empty-state message.
    - test_status_indicator_pending: render todo with status='pending' → zinc circle icon.
    - test_status_indicator_in_progress: status='in_progress' → purple pulsing/spinning indicator.
    - test_status_indicator_completed: status='completed' → green check icon.
    - test_panel_hydrates_on_mount: mock fetchThreadTodos; render at thread mount → fetchThreadTodos called once with the current thread_id; state.todos populated from response.
    - test_panel_responds_to_sse_event: mount with empty todos, dispatch SSE event `{type: 'todos_updated', todos: [{...}]}` through state; assert panel re-renders with new todos.
    - test_panel_no_glass: assert PlanPanel root element does NOT have `backdrop-blur-*` class (CLAUDE.md rule).
    - test_panel_collapsible: panel can be collapsed and expanded via the same affordance as SubAgentPanel.

    Run tests:
    ```
    cd frontend && npx vitest run src/components/chat/__tests__/PlanPanel.test.tsx
    ```
    Expect ~10 failures (component / state slice not yet implemented — RED).
  </action>
  <verify>
    <automated>cd frontend && grep -q "type Todo" src/types/index.ts && grep -q "fetchThreadTodos" src/lib/api.ts && grep -q "TODOS_UPDATED" src/hooks/useChatState.tsx && npx vitest run src/components/chat/__tests__/PlanPanel.test.tsx 2>&1 | grep -cE "FAIL|fail" | grep -q "[1-9]"</automated>
  </verify>
  <done>Todo type, fetchThreadTodos, reducer extension all in place. ~10 Vitest tests defined and failing (component not built yet — RED).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement PlanPanel.tsx + slot into AppLayout</name>
  <files>frontend/src/components/chat/PlanPanel.tsx, frontend/src/components/layout/AppLayout.tsx</files>
  <action>
    Create `frontend/src/components/chat/PlanPanel.tsx`:

    ```tsx
    import { Circle, Loader2, CheckCircle2 } from 'lucide-react';
    import { useTranslation } from '@/i18n';
    import { useChatState } from '@/hooks/useChatState';
    import { cn } from '@/lib/utils';
    import type { Todo, TodoStatus } from '@/types';

    function StatusIcon({ status }: { status: TodoStatus }) {
      if (status === 'completed') return <CheckCircle2 size={16} className="text-green-500" data-testid="status-completed" />;
      if (status === 'in_progress') return <Loader2 size={16} className="animate-spin text-purple-500" data-testid="status-in-progress" />;
      return <Circle size={16} className="text-zinc-400" data-testid="status-pending" />;
    }

    export function PlanPanel() {
      const { t } = useTranslation();
      const { state } = useChatState();
      const { todos, isCurrentMessageDeepMode } = state;

      const visible = isCurrentMessageDeepMode || todos.length > 0;
      if (!visible) return null;

      return (
        <aside
          data-testid="plan-panel"
          className={cn(
            "w-80 border-l border-zinc-200 bg-white p-4",
            // NO backdrop-blur — CLAUDE.md persistent-panel rule
          )}
          aria-label={t('planPanel.title')}
        >
          <h3 className="mb-3 text-sm font-semibold">{t('planPanel.title')}</h3>
          {todos.length === 0 ? (
            <p className="text-sm text-zinc-500">{t('planPanel.empty')}</p>
          ) : (
            <ol className="space-y-2">
              {todos
                .slice()
                .sort((a, b) => a.position - b.position)
                .map(todo => (
                  <li key={todo.id} className="flex items-start gap-2">
                    <StatusIcon status={todo.status} />
                    <span
                      className={cn(
                        "text-sm",
                        todo.status === 'completed' && "line-through text-zinc-400"
                      )}
                    >
                      {todo.content}
                    </span>
                  </li>
                ))}
            </ol>
          )}
        </aside>
      );
    }
    ```

    Slot into `frontend/src/components/layout/AppLayout.tsx` near where SubAgentPanel and CodeExecutionPanel are mounted:

    ```tsx
    <PlanPanel />
    {/* existing panels */}
    ```

    The collapse behavior is inherited from the surrounding sidebar shell (per D-22, AppLayout already has the slot semantics; PlanPanel just renders or returns null based on visibility logic).

    Re-run tests:
    ```
    cd frontend && npx vitest run src/components/chat/__tests__/PlanPanel.test.tsx
    cd frontend && npx tsc --noEmit && npm run lint
    ```
    All ~10 tests should pass; no tsc / lint errors.
  </action>
  <verify>
    <automated>cd frontend && test -f src/components/chat/PlanPanel.tsx && grep -q "PlanPanel" src/components/layout/AppLayout.tsx && npx vitest run src/components/chat/__tests__/PlanPanel.test.tsx 2>&1 | tail -3 | grep -qE "passed" && npx tsc --noEmit 2>&1 | grep -E "error" | grep -v "^$" | wc -l | grep -q "^0"</automated>
  </verify>
  <done>PlanPanel.tsx implemented, slotted into AppLayout. All ~10 tests pass. tsc + lint clean. NO glass / backdrop-blur on the panel surface.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client→backend (GET /todos) | Client must respect RLS-scoped response; no cross-thread fetch |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-17-16 | I (Information Disclosure) | client renders todos belonging to wrong thread | mitigate | useEffect resets todos when thread_id changes; fetchThreadTodos always called with current thread_id; backend RLS authoritative (Plan 17-05 mitigates server-side) |

</threat_model>

<verification>
- PlanPanel renders correctly across all 3 visibility states (hidden / with-todos / deep-mode-active-no-todos).
- Status indicators map correctly.
- Hydration on thread mount via fetchThreadTodos.
- SSE event drives state updates.
- ~10 Vitest tests pass.
- No backdrop-blur on panel.
- tsc + lint clean.
- AppLayout slot live; panel coexists with SubAgentPanel + CodeExecutionPanel.
</verification>

<success_criteria>
- TODO-06 covered: real-time Plan Panel sidebar with pending/in_progress/completed visual differentiation.
- TODO-07 covered: thread reload restores last-known todo state via fetchThreadTodos.
- D-22 visibility rule honored: panel survives after a deep run (todos.length > 0 keeps it visible).
- D-25 status indicators implemented.
- D-26 reducer-driven state.
- CLAUDE.md panel rule honored: no glass on persistent panel.
- Phase 17 success criteria #2 (Plan Panel streaming todos_updated) and #3 (reload reconstruction) both observably satisfied end-to-end.
</success_criteria>

<output>
After completion, create `.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-07-SUMMARY.md`
</output>
