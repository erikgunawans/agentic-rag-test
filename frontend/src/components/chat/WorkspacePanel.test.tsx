/**
 * Phase 18 / WS-07 / WS-08 / WS-11
 * Vitest tests for WorkspacePanel sidebar component.
 *
 * Test coverage (7 behaviors):
 *   1. Panel renders nothing when files.length === 0 (WS-11)
 *   2. Populated: file row with path, size badge, agent source badge
 *   3. Clicking a text file fetches content and renders inline view
 *   4. Clicking a binary file calls window.open with the GET endpoint URL
 *   5. Multiple files render in the order provided (most recent first)
 *   6. Source badges render with correct color class for each source variant
 *   7. Collapse button toggles the file list visibility
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { I18nProvider } from '@/i18n/I18nContext'
import { WorkspacePanel } from './WorkspacePanel'
import type { WorkspaceFile } from '@/hooks/useChatState'

// ---------------------------------------------------------------------------
// Mock apiFetch — simulates GET /threads/{id}/files/{path} returning text
// ---------------------------------------------------------------------------
vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(async (url: string) => ({
    text: async () => `# content of ${url}`,
    json: async () => ({}),
  })),
}))

import { apiFetch } from '@/lib/api'

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const NOW = new Date().toISOString()

const FILE_TEXT: WorkspaceFile = {
  file_path: 'notes/x.md',
  size_bytes: 5,
  source: 'agent',
  mime_type: 'text/markdown',
  updated_at: NOW,
}

const FILE_BINARY: WorkspaceFile = {
  file_path: 'diagrams/arch.png',
  size_bytes: 40960,
  source: 'sandbox',
  mime_type: 'image/png',
  updated_at: NOW,
}

const FILE_UPLOAD: WorkspaceFile = {
  file_path: 'docs/contract.pdf',
  size_bytes: 102400,
  source: 'upload',
  mime_type: 'application/pdf',
  updated_at: NOW,
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPanel(
  files: WorkspaceFile[],
  threadId = 'T',
) {
  return render(
    <I18nProvider>
      <WorkspacePanel threadId={threadId} files={files} />
    </I18nProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('open', vi.fn())
  // Set locale to English so badge text matches 'agent' / 'sandbox' / 'upload'
  localStorage.setItem('locale', 'en')
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('WorkspacePanel', () => {
  // Test 1: WS-11 — panel hidden when no files
  it('renders nothing when files is empty', () => {
    const { container } = renderPanel([])
    expect(container.firstChild).toBeNull()
  })

  // Test 2: populated — file row with path, size badge, source badge
  it('renders a file row with path, size badge, and agent source badge', () => {
    renderPanel([FILE_TEXT])

    expect(screen.getByText('notes/x.md')).toBeInTheDocument()
    // formatBytes(5) → "5 B"
    expect(screen.getByText('5 B')).toBeInTheDocument()
    // Agent source badge (English: "agent")
    expect(screen.getByTestId('source-badge-agent')).toBeInTheDocument()
    expect(screen.getByTestId('source-badge-agent').textContent).toBe('agent')
  })

  // Test 3: clicking a text file fetches content and renders inline view
  it('clicking a text file fetches content and shows inline view', async () => {
    renderPanel([FILE_TEXT], 'T')

    const fileBtn = screen.getByTestId('workspace-file-notes/x.md')
    fireEvent.click(fileBtn)

    await waitFor(() => {
      const contentEl = screen.queryByTestId('workspace-content-notes/x.md')
      expect(contentEl).not.toBeNull()
    })

    // apiFetch called with the encoded file path
    expect(apiFetch).toHaveBeenCalledWith(
      expect.stringContaining('/threads/T/files/notes%2Fx.md'),
    )

    // Content rendered in inline view
    const contentEl = screen.getByTestId('workspace-content-notes/x.md')
    expect(contentEl).toBeInTheDocument()
    expect(contentEl.textContent).toContain('content of')
  })

  // Test 4: clicking a binary file calls window.open with GET endpoint URL
  it('clicking a binary file calls window.open with the download URL', () => {
    renderPanel([FILE_BINARY], 'T')

    const fileBtn = screen.getByTestId('workspace-file-diagrams/arch.png')
    fireEvent.click(fileBtn)

    expect(window.open).toHaveBeenCalledTimes(1)
    expect(window.open).toHaveBeenCalledWith(
      expect.stringContaining('/threads/T/files/diagrams%2Farch.png'),
      '_blank',
      'noopener,noreferrer',
    )
    // apiFetch should NOT be called for binary files
    expect(apiFetch).not.toHaveBeenCalled()
  })

  // Test 5: multiple files render in the order provided
  it('renders multiple files in the order provided', () => {
    renderPanel([FILE_TEXT, FILE_BINARY, FILE_UPLOAD])

    // All three file buttons are rendered
    expect(screen.getByTestId('workspace-file-notes/x.md')).toBeInTheDocument()
    expect(screen.getByTestId('workspace-file-diagrams/arch.png')).toBeInTheDocument()
    expect(screen.getByTestId('workspace-file-docs/contract.pdf')).toBeInTheDocument()

    // Order: notes/x.md precedes diagrams/arch.png (DOM order = prop order)
    const noteBtn = screen.getByTestId('workspace-file-notes/x.md')
    const archBtn = screen.getByTestId('workspace-file-diagrams/arch.png')
    const order = noteBtn.compareDocumentPosition(archBtn)
    expect(order & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  // Test 6: source badges render with correct color class for each variant
  it('source badges use variant-specific color classes', () => {
    renderPanel([FILE_TEXT, FILE_BINARY, FILE_UPLOAD])

    const agentBadge = screen.getByTestId('source-badge-agent')
    const sandboxBadge = screen.getByTestId('source-badge-sandbox')
    const uploadBadge = screen.getByTestId('source-badge-upload')

    expect(agentBadge.className).toContain('bg-purple-500/20')
    expect(sandboxBadge.className).toContain('bg-blue-500/20')
    expect(uploadBadge.className).toContain('bg-zinc-500/20')
  })

  // Test 7: collapse button toggles the file list visibility
  it('collapse button hides and restores the file list', async () => {
    renderPanel([FILE_TEXT])

    // Files visible initially
    expect(screen.getByTestId('workspace-file-notes/x.md')).toBeInTheDocument()

    // Find collapse button
    const collapseBtn = screen.getByRole('button', { name: /collapse|sembunyikan/i })
    fireEvent.click(collapseBtn)

    // Files hidden after collapse
    await waitFor(() => {
      expect(screen.queryByTestId('workspace-file-notes/x.md')).toBeNull()
    })

    // Expand again
    const expandBtn = screen.getByRole('button', { name: /expand|tampilkan/i })
    fireEvent.click(expandBtn)

    await waitFor(() => {
      expect(screen.getByTestId('workspace-file-notes/x.md')).toBeInTheDocument()
    })
  })
})
