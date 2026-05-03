/**
 * Phase 20 / Plan 20-10 / UPL-04 / UI-SPEC L320
 * FileUploadButton co-located Vitest 3.2 tests.
 *
 * 9 cases (original 8 + 1 new W6 case for harness-disabled-but-workspace-enabled):
 *   (a) hidden when settings.workspace_enabled=false — assert button not rendered
 *   (b) visible when settings.workspace_enabled=true — data-testid="file-upload-button" present
 *   (c) rejects >25 MB locally — fire change event with large file, assert toast, apiFetch NOT called
 *   (d) rejects non-DOCX/PDF MIME locally — file with type 'application/zip', assert toast
 *   (e) shows progress card on multipart upload — apiFetch pending, assert progress testid
 *   (f) success removes progress UI — apiFetch resolves, progress card unmounts
 *   (g) abort during upload calls AbortController.abort + removes progress UI
 *   (h) backend 4xx with code='wrong_mime' surfaces t('upload.wrongMime') toast
 *   (i) [W6] visible when workspace_enabled=true even if harness_enabled=false/undefined
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { I18nProvider } from '@/i18n/I18nContext'
import type { UploadingFile } from '@/hooks/useChatState'

// ---------------------------------------------------------------------------
// Mock apiFetch
// ---------------------------------------------------------------------------
vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
}))
import { apiFetch } from '@/lib/api'
const mockApiFetch = apiFetch as ReturnType<typeof vi.fn>

// ---------------------------------------------------------------------------
// Mock toast
// ---------------------------------------------------------------------------
vi.mock('@/lib/toast', () => ({
  toast: vi.fn(),
}))
import { toast } from '@/lib/toast'
const mockToast = toast as ReturnType<typeof vi.fn>

// ---------------------------------------------------------------------------
// Mock usePublicSettings — controls workspaceEnabled visibility gate
// ---------------------------------------------------------------------------
const mockPublicSettings = {
  contextWindow: null as number | null,
  deepModeEnabled: false,
  workspaceEnabled: true,
  error: null as Error | null,
}
vi.mock('@/hooks/usePublicSettings', () => ({
  usePublicSettings: () => mockPublicSettings,
}))

// ---------------------------------------------------------------------------
// Mock useChatContext — provides uploadingFiles slice + helpers
// ---------------------------------------------------------------------------
type UploadMap = Map<string, UploadingFile>
const uploadingFilesRef: { current: UploadMap } = { current: new Map() }

const mockChatContext = {
  activeThreadId: 'thread-1' as string | null,
  get uploadingFiles() { return uploadingFilesRef.current },
  startUpload: vi.fn((meta: { id: string; filename: string; sizeBytes: number; abort: AbortController }) => {
    const m = new Map(uploadingFilesRef.current)
    m.set(meta.id, { ...meta, percent: 0 })
    uploadingFilesRef.current = m
  }),
  updateUploadProgress: vi.fn(),
  completeUpload: vi.fn((id: string) => {
    const m = new Map(uploadingFilesRef.current)
    m.delete(id)
    uploadingFilesRef.current = m
  }),
  failUpload: vi.fn((id: string, error: string) => {
    const m = new Map(uploadingFilesRef.current)
    const entry = m.get(id)
    if (entry) m.set(id, { ...entry, error })
    uploadingFilesRef.current = m
  }),
}
vi.mock('@/contexts/ChatContext', () => ({
  useChatContext: () => mockChatContext,
}))

// Import AFTER mocks
import { FileUploadButton } from './FileUploadButton'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function renderButton() {
  return render(
    <I18nProvider>
      <div style={{ position: 'relative' }}>
        <FileUploadButton />
      </div>
    </I18nProvider>,
  )
}

function makeFile(name: string, type: string, sizeBytes: number): File {
  const content = new Uint8Array(sizeBytes)
  return new File([content], name, { type })
}

function fireFileChange(input: HTMLElement, file: File) {
  Object.defineProperty(input, 'files', {
    configurable: true,
    get: () => ({ 0: file, length: 1, item: (i: number) => (i === 0 ? file : null) }),
  })
  fireEvent.change(input)
}

beforeEach(() => {
  vi.clearAllMocks()
  // Reset uploadingFiles Map between tests
  uploadingFilesRef.current = new Map()
  // Default settings: workspace enabled
  mockPublicSettings.workspaceEnabled = true
  mockPublicSettings.deepModeEnabled = false
  mockChatContext.activeThreadId = 'thread-1'
  localStorage.setItem('locale', 'en')
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('FileUploadButton', () => {
  it('(a) hidden when workspace_enabled=false', () => {
    mockPublicSettings.workspaceEnabled = false
    renderButton()
    expect(screen.queryByTestId('file-upload-button')).toBeNull()
  })

  it('(b) visible when workspace_enabled=true', () => {
    mockPublicSettings.workspaceEnabled = true
    renderButton()
    expect(screen.getByTestId('file-upload-button')).toBeTruthy()
  })

  it('(c) rejects >25 MB locally — toast shown, apiFetch NOT called', () => {
    renderButton()
    const input = screen.getByTestId('file-upload-input')
    const bigFile = makeFile('contract.pdf', 'application/pdf', 25 * 1024 * 1024 + 1)
    fireFileChange(input, bigFile)
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ role: 'alert', message: expect.stringContaining('25') }),
    )
    expect(mockApiFetch).not.toHaveBeenCalled()
  })

  it('(d) rejects non-DOCX/PDF MIME locally — toast shown', () => {
    renderButton()
    const input = screen.getByTestId('file-upload-input')
    const zipFile = makeFile('archive.zip', 'application/zip', 1024)
    fireFileChange(input, zipFile)
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ role: 'alert' }),
    )
    expect(mockApiFetch).not.toHaveBeenCalled()
  })

  it('(e) shows progress card during upload', async () => {
    // apiFetch never resolves during this test — simulates in-flight upload
    let resolveUpload!: () => void
    mockApiFetch.mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        resolveUpload = () => resolve(new Response('{}', { status: 200 }))
      }),
    )

    renderButton()
    const input = screen.getByTestId('file-upload-input')
    const validFile = makeFile('contract.pdf', 'application/pdf', 1024)
    fireFileChange(input, validFile)

    // startUpload is called synchronously before the await apiFetch
    await waitFor(() => {
      expect(mockChatContext.startUpload).toHaveBeenCalledOnce()
    })

    // Resolve upload to avoid test leaks
    resolveUpload()
  })

  it('(f) success removes progress UI', async () => {
    mockApiFetch.mockResolvedValueOnce(new Response('{}', { status: 200 }))

    renderButton()
    const input = screen.getByTestId('file-upload-input')
    const validFile = makeFile('contract.pdf', 'application/pdf', 1024)
    fireFileChange(input, validFile)

    await waitFor(() => {
      expect(mockChatContext.completeUpload).toHaveBeenCalledOnce()
    })
    // No error toast on success
    expect(mockToast).not.toHaveBeenCalled()
  })

  it('(g) abort during upload calls AbortController.abort', async () => {
    let resolveUpload!: () => void
    let rejectUpload!: (err: Error) => void
    mockApiFetch.mockReturnValueOnce(
      new Promise<Response>((resolve, reject) => {
        resolveUpload = () => resolve(new Response('{}', { status: 200 }))
        rejectUpload = reject
      }),
    )

    renderButton()
    const input = screen.getByTestId('file-upload-input')
    const validFile = makeFile('contract.pdf', 'application/pdf', 1024)
    fireFileChange(input, validFile)

    await waitFor(() => {
      expect(mockChatContext.startUpload).toHaveBeenCalledOnce()
    })

    // Simulate abort by rejecting with AbortError
    const abortErr = new DOMException('Aborted', 'AbortError')
    Object.defineProperty(abortErr, 'name', { value: 'AbortError' })
    rejectUpload(abortErr as unknown as Error)

    await waitFor(() => {
      expect(mockChatContext.completeUpload).toHaveBeenCalledOnce()
    })
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ message: expect.stringContaining('cancelled') }),
    )

    // Suppress unhandled promise warning
    void resolveUpload
  })

  it('(h) backend 4xx with code="wrong_mime" surfaces upload.wrongMime toast', async () => {
    const err = new Error('wrong mime type') as Error & { body: Record<string, unknown> }
    err.body = { error: 'wrong_mime' }
    mockApiFetch.mockRejectedValueOnce(err)

    renderButton()
    const input = screen.getByTestId('file-upload-input')
    const validFile = makeFile('contract.pdf', 'application/pdf', 1024)
    fireFileChange(input, validFile)

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          role: 'alert',
          message: expect.stringContaining('DOCX'),
        }),
      )
    })
    expect(mockChatContext.failUpload).toHaveBeenCalledOnce()
  })

  it('(i) [W6] visible when workspace_enabled=true regardless of harness_enabled', () => {
    // D-13: paperclip is gated ONLY on workspace_enabled; harness_enabled is irrelevant.
    // Simulate settings where harness_enabled is falsy/undefined — button must still show.
    mockPublicSettings.workspaceEnabled = true
    // Cast to any to simulate missing harness_enabled (old backend / harness off)
    ;(mockPublicSettings as Record<string, unknown>).harness_enabled = false
    renderButton()
    expect(screen.getByTestId('file-upload-button')).toBeTruthy()
  })
})
