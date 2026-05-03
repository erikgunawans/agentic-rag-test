/**
 * Phase 19 / TASK-07 / D-25 — Vitest tests for TaskPanel.
 *
 * 9 tests covering:
 *   1. renders nothing when tasks.size === 0
 *   2. renders one card per task entry
 *   3. running task shows Loader2 spinner with animate-spin and text-purple-500
 *   4. complete task shows CheckCircle2 and result preview with line-clamp-2
 *   5. error task shows AlertCircle and error detail in red
 *   6. context_files render as truncated chips with title attribute
 *   7. nested tool calls render with font-mono text-[11px]
 *   8. collapse button toggles content area
 *   9. has role=complementary and aria-label
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nProvider } from '@/i18n/I18nContext'
import { TaskPanel } from './TaskPanel'
import type { TaskState } from '@/hooks/useChatState'

// Mock useChatContext so tests control the tasks Map independently.
vi.mock('@/contexts/ChatContext', () => ({
  useChatContext: vi.fn(),
}))

import { useChatContext } from '@/contexts/ChatContext'

const mockUseChatContext = useChatContext as ReturnType<typeof vi.fn>

function makeTask(overrides: Partial<TaskState> & { taskId: string; description: string; status: TaskState['status'] }): TaskState {
  return {
    contextFiles: [],
    toolCalls: [],
    ...overrides,
  }
}

function renderPanel(tasks: Map<string, TaskState>) {
  localStorage.setItem('locale', 'en')
  mockUseChatContext.mockReturnValue({ tasks })
  return render(
    <I18nProvider>
      <TaskPanel />
    </I18nProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.setItem('locale', 'en')
})

// Shared task fixtures
const RUNNING_TASK = makeTask({
  taskId: 'task-1',
  description: 'Analyze the contract clauses',
  status: 'running',
  contextFiles: ['docs/contract.pdf', 'templates/clause-library.md'],
  toolCalls: [{ toolCallId: 'call-a', tool: 'search_documents' }],
})

const COMPLETE_TASK = makeTask({
  taskId: 'task-2',
  description: 'Generate executive summary',
  status: 'complete',
  result: 'The contract contains 15 risk clauses requiring review.',
})

const ERROR_TASK = makeTask({
  taskId: 'task-3',
  description: 'Extract regulatory references',
  status: 'error',
  error: { error: 'TOOL_FAILED', code: 'E001', detail: 'Regulatory DB unreachable' },
})

describe('TaskPanel', () => {
  it('renders nothing when tasks size is zero', () => {
    const { container } = renderPanel(new Map())
    expect(container.firstChild).toBeNull()
  })

  it('renders one card per task entry', () => {
    const tasks = new Map<string, TaskState>([
      ['task-1', RUNNING_TASK],
      ['task-2', COMPLETE_TASK],
      ['task-3', ERROR_TASK],
    ])
    renderPanel(tasks)
    // Each task description rendered
    expect(screen.getByText('Analyze the contract clauses')).toBeInTheDocument()
    expect(screen.getByText('Generate executive summary')).toBeInTheDocument()
    expect(screen.getByText('Extract regulatory references')).toBeInTheDocument()
  })

  it('running task shows Loader2 spinner with animate-spin and text-purple-500', () => {
    const tasks = new Map<string, TaskState>([['task-1', RUNNING_TASK]])
    const { container } = renderPanel(tasks)
    // Loader2 renders as lucide-loader-circle SVG with animate-spin + text-purple-500 classes
    const spinnerSvg = container.querySelector('svg.lucide-loader-circle')
    expect(spinnerSvg).not.toBeNull()
    // SVG className is an SVGAnimatedString — use getAttribute('class') for assertions
    const spinnerClasses = spinnerSvg?.getAttribute('class') ?? ''
    expect(spinnerClasses).toContain('animate-spin')
    expect(spinnerClasses).toContain('text-purple-500')
  })

  it('complete task shows CheckCircle2 and result preview with line-clamp-2', () => {
    const tasks = new Map<string, TaskState>([['task-2', COMPLETE_TASK]])
    const { container } = renderPanel(tasks)
    // CheckCircle2 (lucide-circle-check)
    const checkIcon = container.querySelector('svg.lucide-circle-check')
    expect(checkIcon).not.toBeNull()
    // Result preview rendered with line-clamp-2
    const resultEl = screen.getByText('The contract contains 15 risk clauses requiring review.')
    expect(resultEl).toBeInTheDocument()
    expect(resultEl.className).toContain('line-clamp-2')
  })

  it('error task shows AlertCircle and error detail in red', () => {
    const tasks = new Map<string, TaskState>([['task-3', ERROR_TASK]])
    const { container } = renderPanel(tasks)
    // AlertCircle (lucide-circle-alert)
    const alertIcon = container.querySelector('svg.lucide-circle-alert')
    expect(alertIcon).not.toBeNull()
    // Error detail text rendered
    const errorEl = screen.getByText('Regulatory DB unreachable')
    expect(errorEl).toBeInTheDocument()
    // Red color class
    expect(errorEl.className).toMatch(/text-red-/)
  })

  it('context_files render as truncated chips with title attribute for tooltip', () => {
    const tasks = new Map<string, TaskState>([['task-1', RUNNING_TASK]])
    const { container } = renderPanel(tasks)
    // Both context files rendered as chips
    const chips = container.querySelectorAll('span[title]')
    const paths = Array.from(chips).map((c) => c.getAttribute('title'))
    expect(paths).toContain('docs/contract.pdf')
    expect(paths).toContain('templates/clause-library.md')
    // Each chip has the truncate class
    for (const chip of Array.from(chips)) {
      expect(chip.className).toContain('truncate')
    }
  })

  it('nested tool calls list renders with font-mono text-[11px]', () => {
    const tasks = new Map<string, TaskState>([['task-1', RUNNING_TASK]])
    const { container } = renderPanel(tasks)
    // Tool name span inside nested list
    const toolSpan = container.querySelector('.font-mono.text-\\[11px\\]')
    expect(toolSpan).not.toBeNull()
    expect(toolSpan?.textContent).toBe('search_documents')
  })

  it('collapse button toggles content area', async () => {
    const user = userEvent.setup()
    const tasks = new Map<string, TaskState>([['task-2', COMPLETE_TASK]])
    renderPanel(tasks)

    // Content visible initially
    expect(screen.getByText('Generate executive summary')).toBeInTheDocument()

    // Click collapse button
    const collapseBtn = screen.getByRole('button', { name: /collapse/i })
    await user.click(collapseBtn)

    // Content hidden after collapse
    expect(screen.queryByText('Generate executive summary')).toBeNull()

    // Click expand button
    const expandBtn = screen.getByRole('button', { name: /expand/i })
    await user.click(expandBtn)

    // Content visible again
    expect(screen.getByText('Generate executive summary')).toBeInTheDocument()
  })

  it('has role=complementary and aria-label on the aside element', () => {
    const tasks = new Map<string, TaskState>([['task-2', COMPLETE_TASK]])
    renderPanel(tasks)
    const aside = screen.getByRole('complementary')
    expect(aside).not.toBeNull()
    expect(aside.getAttribute('aria-label')).toBeTruthy()
  })
})
