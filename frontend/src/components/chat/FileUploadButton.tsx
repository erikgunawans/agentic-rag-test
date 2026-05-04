/**
 * Phase 20 / Plan 20-10 / UPL-04: Paperclip file-upload button.
 *
 * Visibility: shown when usePublicSettings().workspaceEnabled is true.
 * Per CONTEXT.md D-13 (W6 fix), the paperclip is ALWAYS visible when
 * WORKSPACE_ENABLED=true — works for both harness flows AND general workspace
 * upload (when no harness is registered, file lands as source='upload').
 *
 * Geometry: byte-identical class string to the existing Plus/FileText buttons
 * in InputActionBar (UI-SPEC L146) — visual consistency contract.
 */
import { useRef } from 'react'
import { Paperclip, Loader2, X } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { useChatContext } from '@/contexts/ChatContext'
import { apiFetch } from '@/lib/api'
import { usePublicSettings } from '@/hooks/usePublicSettings'
import { toast } from '@/lib/toast'

const MAX_BYTES = 25 * 1024 * 1024

const ACCEPTED_MIME: Record<string, true> = {
  'application/pdf': true,
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': true,
}

function uuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `up-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function FileUploadButton() {
  const { t } = useI18n()
  const {
    activeThreadId,
    uploadingFiles,
    startUpload,
    completeUpload,
    failUpload,
    // updateUploadProgress is not used in v1.3: fetch() has no upload progress API.
    // The percent stays at 0 (indeterminate spinner). Swap apiFetch for XHR if fidelity
    // becomes a UAT requirement (see rationale block at end of file).
  } = useChatContext()
  const settings = usePublicSettings()
  const inputRef = useRef<HTMLInputElement>(null)
  const inFlight = uploadingFiles.size > 0

  // W6 fix (per CONTEXT.md D-13): paperclip is ALWAYS visible when WORKSPACE_ENABLED=true.
  // Works for both harness flows AND general workspace upload (when no harness is
  // registered, file lands as source='upload' with no gatekeeper trigger).
  // settings.workspaceEnabled reflects backend workspace_enabled env var via /settings/public.
  if (!settings.workspaceEnabled) return null

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) await handleFile(file)
    // Reset input value so the same file can be re-selected after an error.
    if (inputRef.current) inputRef.current.value = ''
  }

  async function handleFile(file: File) {
    if (!activeThreadId) {
      // CR-21-03 (UAT finding): silent no-op was confusing — the paperclip
      // pill appeared in the input but no /files/upload request fired, so
      // the user thought the file was attached when it wasn't. Surface a
      // toast that points to the correct flow.
      toast({
        role: 'alert',
        message: t('upload.noActiveThread'),
        duration: 5000,
      })
      return
    }

    // Client-side validation (UX only — server re-validates with magic bytes).
    if (file.size > MAX_BYTES) {
      toast({
        role: 'alert',
        message: t('upload.tooLarge', { max: '25' }),
        duration: 5000,
      })
      return
    }
    if (!ACCEPTED_MIME[file.type]) {
      toast({
        role: 'alert',
        message: t('upload.wrongMime'),
        duration: 5000,
      })
      return
    }

    const id = uuid()
    const ctrl = new AbortController()
    startUpload({ id, filename: file.name, sizeBytes: file.size, abort: ctrl })

    const fd = new FormData()
    fd.append('file', file, file.name)

    try {
      await apiFetch(`/threads/${activeThreadId}/files/upload`, {
        method: 'POST',
        body: fd,
        signal: ctrl.signal,
      })
      completeUpload(id)
      // Success path: no toast — file appearing in WorkspacePanel IS the confirmation
      // (workspace_updated SSE fires; WorkspacePanel re-renders with the new file).
    } catch (err: unknown) {
      const e = err as Error & { name?: string; body?: Record<string, unknown>; detail?: Record<string, unknown> }
      if (e?.name === 'AbortError') {
        completeUpload(id)
        toast({ message: t('upload.cancelled'), duration: 3000 })
        return
      }
      // Map backend error code → localized message; never surface raw internals.
      const code = (e?.body?.error ?? e?.detail?.error) as string | undefined
      const localized =
        code === 'wrong_mime' || code === 'magic_byte_mismatch'
          ? t('upload.wrongMime')
          : code === 'upload_too_large'
          ? t('upload.tooLarge', { max: '25' })
          : t('upload.serverError')
      failUpload(id, localized)
      toast({ role: 'alert', message: localized, duration: 5000 })
    }
  }

  return (
    <>
      <button
        type="button"
        data-testid="file-upload-button"
        aria-label={t('chat.attachFile')}
        title={t('chat.attachFile.tooltip')}
        disabled={inFlight}
        onClick={() => inputRef.current?.click()}
        className={
          'flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors ' +
          (inFlight ? 'opacity-50 cursor-not-allowed' : '')
        }
      >
        <Paperclip className="h-4 w-4" />
      </button>
      <input
        ref={inputRef}
        type="file"
        hidden
        accept=".docx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={onPick}
        data-testid="file-upload-input"
      />

      {/* In-flight progress card — one upload at a time per UI-SPEC L154.
          fetch() has no upload progress API, so percent stays 0 (indeterminate
          Loader2 spinner). XHR swap deferred if fidelity becomes a UAT requirement. */}
      {Array.from(uploadingFiles.values()).map((u) => (
        <div
          key={u.id}
          role="status"
          aria-live="polite"
          data-testid="file-upload-progress"
          className="absolute bottom-full left-0 right-0 mx-4 mb-2 bg-card border border-border/50 rounded-lg px-3 py-2 flex items-center gap-2 text-xs"
        >
          <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" aria-hidden />
          <span className="truncate flex-1">
            {t('upload.inProgress', { filename: u.filename, percent: String(u.percent) })}
          </span>
          <button
            type="button"
            data-testid="file-upload-abort"
            aria-label={t('common.cancel')}
            onClick={() => u.abort.abort()}
            className="h-5 w-5 flex items-center justify-center text-muted-foreground hover:text-foreground"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      ))}
    </>
  )
}

// -----------------------------------------------------------------------
// Rationale (W6 fix): paperclip visibility decoupled from harness state.
//
// Per CONTEXT.md D-13, paperclip is "always visible when WORKSPACE_ENABLED=true".
// This delivers two flows from a single button:
//   (1) Harness flow: a registered harness's HarnessPrerequisites
//       declares accepted_mime_types; the gatekeeper sees the new file in
//       workspace and may emit the [TRIGGER_HARNESS] sentinel.
//   (2) General workspace upload: when no harness is registered (or
//       prerequisites are not met), the file simply lands as source='upload'
//       in workspace_files. The agent can reference it later via standard
//       tools (search_workspace, read_workspace_file). No gatekeeper trigger.
//
// The button stays visible in both modes; the SUCCESS path differs only in
// whether a gatekeeper SSE stream eventually fires. The MIME validation lives
// server-side (Plan 20-06): the endpoint's accepted set covers PDF + DOCX
// unconditionally — harness-specific MIME refinement is deferred (no current
// harness narrows beyond PDF/DOCX).
// -----------------------------------------------------------------------
