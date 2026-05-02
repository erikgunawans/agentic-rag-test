import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nProvider } from '@/i18n/I18nContext'
import { CodeExecutionPanel } from './CodeExecutionPanel'

// D-P16-08: mock the network layer; do NOT spin up MSW.
vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
}))
import { apiFetch } from '@/lib/api'

// jsdom doesn't implement window.open; stub it so handleDownload doesn't blow up.
beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('open', vi.fn())
})

const baseProps = {
  toolCallId: 'call-1',
  code: 'print("hi")',
  status: 'success' as const,
  executionMs: 42,
  stdoutLines: [] as string[],
  stderrLines: [] as string[],
  files: [] as Array<{ filename: string; size_bytes: number; signed_url: string }>,
}

function renderPanel(overrides: Partial<Parameters<typeof CodeExecutionPanel>[0]> = {}) {
  return render(
    <I18nProvider>
      <CodeExecutionPanel {...baseProps} {...overrides} />
    </I18nProvider>,
  )
}

function normalize(s: string): string {
  return s.replace(/\s+/g, ' ').trim()
}

describe('CodeExecutionPanel', () => {
  it('streaming output renders stdout/stderr lines in order with color', () => {
    renderPanel({
      status: 'running',
      stdoutLines: ['line A', 'line B'],
      stderrLines: ['err X'],
    })

    const lineA = screen.getByText('line A')
    const lineB = screen.getByText('line B')
    const errX = screen.getByText('err X')

    expect(lineA).toBeInTheDocument()
    expect(lineB).toBeInTheDocument()
    expect(errX).toBeInTheDocument()

    // Order: stdout lines come before stderr lines, in order
    const lineAOrder = lineA.compareDocumentPosition(lineB)
    expect(lineAOrder & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    const lineBToErr = lineB.compareDocumentPosition(errX)
    expect(lineBToErr & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

    // Color classes: stdout green, stderr red
    expect(lineA.className).toMatch(/text-green-/)
    expect(lineB.className).toMatch(/text-green-/)
    expect(errX.className).toMatch(/text-red-/)
  })

  it('terminal block renders dark background and stdout text', () => {
    renderPanel({
      status: 'success',
      stdoutLines: ['hello'],
    })

    const helloLine = screen.getByText('hello')
    expect(helloLine).toBeInTheDocument()

    // Walk up to find the terminal container with the dark background class.
    let el: HTMLElement | null = helloLine
    let foundDarkBg = false
    while (el) {
      if (el.className && /bg-zinc-9/.test(el.className)) {
        foundDarkBg = true
        break
      }
      el = el.parentElement
    }
    expect(foundDarkBg).toBe(true)
  })

  it('Download button calls apiFetch and exposes signed URL', async () => {
    const user = userEvent.setup()
    const mockApiFetch = apiFetch as unknown as ReturnType<typeof vi.fn>
    mockApiFetch.mockResolvedValue({
      json: async () => ({
        files: [
          { filename: 'foo.txt', size_bytes: 100, signed_url: 'https://signed.example/foo' },
        ],
      }),
    })

    renderPanel({
      executionId: 'exec-abc',
      status: 'success',
      files: [
        { filename: 'foo.txt', size_bytes: 100, signed_url: 'https://signed.example/foo' },
      ],
    })

    // Find the Download button by aria-label
    const dlButton = screen.getByRole('button', { name: /foo\.txt/i })
    expect(dlButton).toBeInTheDocument()
    expect(dlButton).not.toBeDisabled()

    await user.click(dlButton)

    expect(mockApiFetch).toHaveBeenCalledTimes(1)
    expect(mockApiFetch).toHaveBeenCalledWith(
      expect.stringContaining('/code-executions/exec-abc'),
    )
    // D-P16-10: do NOT assert real navigation. We only assert window.open was invoked.
    expect(window.open).toHaveBeenCalledWith(
      expect.stringContaining('/foo'),
      expect.any(String),
      expect.any(String),
    )
  })

  it('history-reconstruction parity with streaming render', () => {
    // Render once with "live" streaming data
    const liveProps = {
      ...baseProps,
      status: 'success' as const,
      stdoutLines: ['hello world'],
      stderrLines: ['oops'],
    }
    const { container: liveContainer, unmount: unmountLive } = renderPanel(liveProps)
    const liveText = normalize(liveContainer.textContent ?? '')
    unmountLive()

    // Render second instance with the same data shape but coming from the
    // persisted output object (msg.tool_calls.calls[N].output) — caller still
    // hands us stdoutLines / stderrLines arrays of the same shape per Plan 11
    // D-P11-02.
    const persisted = {
      stdout: ['hello world'],
      stderr: ['oops'],
      status: 'success' as const,
      execution_ms: 42,
    }
    const reconstructedProps = {
      ...baseProps,
      status: persisted.status,
      stdoutLines: persisted.stdout,
      stderrLines: persisted.stderr,
      executionMs: persisted.execution_ms,
    }
    const { container: persistedContainer } = renderPanel(reconstructedProps)
    const persistedText = normalize(persistedContainer.textContent ?? '')

    expect(persistedText).toBe(liveText)
  })

  it('executionId undefined disables Download', () => {
    renderPanel({
      executionId: undefined,
      status: 'success',
      files: [
        { filename: 'foo.txt', size_bytes: 100, signed_url: 'https://signed.example/foo' },
      ],
    })

    const dlButton = screen.queryByRole('button', { name: /foo\.txt/i })
    if (dlButton) {
      expect(dlButton).toBeDisabled()
    } else {
      // alternative: button not rendered
      expect(dlButton).toBeNull()
    }
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('status timeout renders Clock icon', () => {
    const { container } = renderPanel({
      status: 'timeout',
      stdoutLines: [],
      stderrLines: [],
    })

    // lucide-react renders SVGs with class containing "lucide-clock"
    const clockSvg = container.querySelector('svg.lucide-clock')
    expect(clockSvg).not.toBeNull()
  })
})
