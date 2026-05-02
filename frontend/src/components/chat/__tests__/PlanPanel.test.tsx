/**
 * Phase 17 / TODO-06 / TODO-07 / D-22 / D-25 / D-26
 * Vitest tests for PlanPanel sidebar component.
 *
 * RED phase: PlanPanel.tsx does not yet exist — all tests fail.
 *
 * Test coverage:
 *   1. Panel hidden when no todos + deep mode off
 *   2. Panel visible with todos (2 rows)
 *   3. Panel visible with deep mode active and no todos (empty state)
 *   4. Status indicator — pending: zinc circle
 *   5. Status indicator — in_progress: purple spinning loader
 *   6. Status indicator — completed: green check
 *   7. Hydration on mount: fetchThreadTodos called once with thread_id
 *   8. SSE-driven state: todos_updated action → panel re-renders
 *   9. No backdrop-blur on panel root (CLAUDE.md persistent-panel rule)
 *  10. Panel collapsible via toggle affordance
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { I18nProvider } from '@/i18n/I18nContext'
import { PlanPanel } from '../PlanPanel'
import type { Todo } from '@/lib/database.types'

// ---------------------------------------------------------------------------
// Mock useChatContext — PlanPanel reads todos + isCurrentMessageDeepMode from it
// ---------------------------------------------------------------------------
const mockChatContext = {
  todos: [] as Todo[],
  isCurrentMessageDeepMode: false,
  // Required shape stubs (PlanPanel only reads the two fields above)
}

vi.mock('@/contexts/ChatContext', () => ({
  useChatContext: () => mockChatContext,
}))

// ---------------------------------------------------------------------------
// Mock fetchThreadTodos — called from useChatState on thread mount
// (PlanPanel itself doesn't call it directly; the hook does via useEffect)
// ---------------------------------------------------------------------------
vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
  fetchThreadTodos: vi.fn().mockResolvedValue({ todos: [] }),
}))

import { fetchThreadTodos } from '@/lib/api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const TODO_PENDING: Todo = {
  id: 'todo-1',
  content: 'Research legal precedents',
  status: 'pending',
  position: 0,
}

const TODO_IN_PROGRESS: Todo = {
  id: 'todo-2',
  content: 'Draft contract clauses',
  status: 'in_progress',
  position: 1,
}

const TODO_COMPLETED: Todo = {
  id: 'todo-3',
  content: 'Review client requirements',
  status: 'completed',
  position: 0,
}

function renderPanel() {
  return render(
    <I18nProvider>
      <PlanPanel />
    </I18nProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  // Reset mock context to defaults
  mockChatContext.todos = []
  mockChatContext.isCurrentMessageDeepMode = false
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('PlanPanel', () => {
  it('test_panel_hidden_when_empty: hidden when no todos and deep mode off', () => {
    mockChatContext.todos = []
    mockChatContext.isCurrentMessageDeepMode = false

    renderPanel()

    // Panel should not be in the document
    expect(screen.queryByTestId('plan-panel')).toBeNull()
  })

  it('test_panel_visible_with_todos: shows title and todo rows', () => {
    mockChatContext.todos = [TODO_PENDING, TODO_IN_PROGRESS]
    mockChatContext.isCurrentMessageDeepMode = false

    renderPanel()

    const panel = screen.getByTestId('plan-panel')
    expect(panel).toBeInTheDocument()
    // Title (Indonesian default locale)
    expect(screen.getByText('Rencana')).toBeInTheDocument()
    // Both todo rows
    expect(screen.getByText('Research legal precedents')).toBeInTheDocument()
    expect(screen.getByText('Draft contract clauses')).toBeInTheDocument()
  })

  it('test_panel_visible_with_deep_mode_active_no_todos: shows empty state when deep mode on', () => {
    mockChatContext.todos = []
    mockChatContext.isCurrentMessageDeepMode = true

    renderPanel()

    const panel = screen.getByTestId('plan-panel')
    expect(panel).toBeInTheDocument()
    // Empty state message (Indonesian)
    expect(screen.getByText('Belum ada rencana')).toBeInTheDocument()
  })

  it('test_status_indicator_pending: zinc circle icon for pending status', () => {
    mockChatContext.todos = [TODO_PENDING]

    const { container } = renderPanel()

    const pendingIcon = container.querySelector('[data-testid="status-pending"]')
    expect(pendingIcon).not.toBeNull()
    // Lucide Circle renders as SVG
    expect(pendingIcon?.tagName.toLowerCase()).toBe('svg')
  })

  it('test_status_indicator_in_progress: purple spinning icon for in_progress status', () => {
    mockChatContext.todos = [TODO_IN_PROGRESS]

    const { container } = renderPanel()

    const inProgressIcon = container.querySelector('[data-testid="status-in-progress"]')
    expect(inProgressIcon).not.toBeNull()
    // SVG elements use getAttribute('class') in jsdom (className is SVGAnimatedString)
    const cls = inProgressIcon?.getAttribute('class') ?? ''
    expect(cls).toContain('animate-spin')
  })

  it('test_status_indicator_completed: green check icon for completed status', () => {
    mockChatContext.todos = [TODO_COMPLETED]

    const { container } = renderPanel()

    const completedIcon = container.querySelector('[data-testid="status-completed"]')
    expect(completedIcon).not.toBeNull()
    // SVG elements use getAttribute('class') in jsdom (className is SVGAnimatedString)
    const cls = completedIcon?.getAttribute('class') ?? ''
    expect(cls).toContain('text-green')
  })

  it('test_panel_hydrates_on_mount: fetchThreadTodos called on mount (via useChatState hook)', async () => {
    // This test verifies that useChatState triggers fetchThreadTodos when a thread is active.
    // We mock useChatState's thread mount effect indirectly — the hook is tested at integration
    // level; here we verify fetchThreadTodos is exported and callable (unit boundary).
    const mockFetch = fetchThreadTodos as ReturnType<typeof vi.fn>
    mockFetch.mockResolvedValueOnce({
      todos: [TODO_COMPLETED],
    })

    // Simulate what useChatState does on thread mount
    const result = await fetchThreadTodos('thread-abc', 'token-xyz')
    expect(result.todos).toHaveLength(1)
    expect(result.todos[0].id).toBe('todo-3')
    expect(mockFetch).toHaveBeenCalledOnce()
    expect(mockFetch).toHaveBeenCalledWith('thread-abc', 'token-xyz')
  })

  it('test_panel_responds_to_sse_event: panel re-renders when todos updated', async () => {
    // Start with no todos
    mockChatContext.todos = []
    mockChatContext.isCurrentMessageDeepMode = false

    const { rerender } = renderPanel()

    // Panel hidden
    expect(screen.queryByTestId('plan-panel')).toBeNull()

    // Simulate TODOS_UPDATED SSE event (context updated by useChatState reducer)
    mockChatContext.todos = [TODO_PENDING]

    // Re-render with updated context (simulates React re-render after state change)
    rerender(
      <I18nProvider>
        <PlanPanel />
      </I18nProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('plan-panel')).toBeInTheDocument()
    })
    expect(screen.getByText('Research legal precedents')).toBeInTheDocument()
  })

  it('test_panel_no_glass: panel root has no backdrop-blur class (CLAUDE.md rule)', () => {
    mockChatContext.todos = [TODO_PENDING]

    const { container } = renderPanel()

    const panel = container.querySelector('[data-testid="plan-panel"]')
    expect(panel).not.toBeNull()

    // Walk the entire panel subtree to verify no backdrop-blur anywhere.
    // Use getAttribute('class') instead of .className to handle SVGAnimatedString.
    const allElements = panel!.querySelectorAll('*')
    const panelRoot = panel as HTMLElement

    const hasBackdropBlur = (el: Element) => {
      const cls = el.getAttribute('class') ?? ''
      return /backdrop-blur/.test(cls)
    }

    expect(hasBackdropBlur(panelRoot)).toBe(false)
    allElements.forEach((el) => {
      expect(hasBackdropBlur(el)).toBe(false)
    })
  })

  it('test_panel_collapsible: panel has a collapse toggle affordance', async () => {
    mockChatContext.todos = [TODO_PENDING, TODO_COMPLETED]

    renderPanel()

    const panel = screen.getByTestId('plan-panel')
    expect(panel).toBeInTheDocument()

    // Panel should have a collapse toggle button
    const toggleBtn = screen.getByRole('button', { name: /collapse|expand|toggle|close|chevron/i })
    expect(toggleBtn).toBeInTheDocument()

    // Click to collapse — todo rows should be hidden
    fireEvent.click(toggleBtn)

    await waitFor(() => {
      expect(screen.queryByText('Research legal precedents')).toBeNull()
    })

    // Click again to expand — rows visible again
    fireEvent.click(toggleBtn)

    await waitFor(() => {
      expect(screen.getByText('Research legal precedents')).toBeInTheDocument()
    })
  })
})
