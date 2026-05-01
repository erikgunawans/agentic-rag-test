import { useEffect, useRef, useState } from 'react'
import {
  Terminal,
  Copy,
  ChevronRight,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  FileDown,
  Download,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n/I18nContext'
import { apiFetch } from '@/lib/api'

// Phase 11 — SANDBOX-07.
// Inline panel rendered inside an assistant message bubble for each
// execute_code tool call. Self-contained: this plan (11-06) does NOT wire it
// into ToolCallList — Plan 11-07 owns the routing switch.
//
// Streaming → persisted reconciliation (D-P11-02):
//   - During streaming: caller passes live arrays from useChatState.sandboxStreams
//     keyed by tool_call_id (per Plan 11-05).
//   - After delta:{done:true} refetch: caller passes the persisted arrays
//     from msg.tool_calls.calls[N].output (stdout / stderr / files / status /
//     execution_ms / error_type). The Map entry has been cleared by then.
//
// Glass rule (CLAUDE.md / UI-SPEC): persistent panel — NO blurred backgrounds,
// NO gradient. Solid bg-card / bg-zinc-900 only.

type SandboxStatus = 'pending' | 'running' | 'success' | 'error' | 'timeout'

interface SandboxFile {
  filename: string
  size_bytes: number
  signed_url: string
}

interface CodeExecutionPanelProps {
  toolCallId: string
  /**
   * code_executions.id — required for refresh-on-click signed-URL roundtrip
   * (D-P11-06 / Plan 11-03 GET /code-executions/{id}). Resolved upstream from
   * `out.execution_id` (sandbox tool_output, see backend
   * sandbox_service.py L284). When undefined (legacy / non-sandbox row) the
   * download button stays disabled — the panel still renders gracefully.
   */
  executionId?: string
  code: string
  status: SandboxStatus
  executionMs?: number
  stdoutLines: string[]
  stderrLines: string[]
  files: SandboxFile[]
  errorType?: string
}

function formatBytes(b: number): string {
  if (b < 1000) return `${b} B`
  if (b < 1_000_000) return `${(b / 1000).toFixed(1)} KB`
  if (b < 1_000_000_000) return `${(b / 1_000_000).toFixed(1)} MB`
  return `${(b / 1_000_000_000).toFixed(2)} GB`
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function CodeExecutionPanel(props: CodeExecutionPanelProps) {
  const { t } = useI18n()
  const {
    executionId,
    code,
    status,
    executionMs,
    stdoutLines,
    stderrLines,
    files,
    errorType,
  } = props

  // D-P11-09: code preview collapsed by default.
  const [codeExpanded, setCodeExpanded] = useState(false)
  const [liveMs, setLiveMs] = useState(0)
  const [downloadingFile, setDownloadingFile] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const terminalRef = useRef<HTMLDivElement>(null)
  const userScrolledRef = useRef(false)
  const startedAtRef = useRef<number | null>(null)

  // Live execution timer — runs while status is pending/running, frozen
  // afterward (final value comes from executionMs).
  useEffect(() => {
    if (status === 'pending' || status === 'running') {
      if (startedAtRef.current === null) startedAtRef.current = Date.now()
      const id = setInterval(() => {
        setLiveMs(Date.now() - (startedAtRef.current ?? Date.now()))
      }, 100)
      return () => clearInterval(id)
    }
    startedAtRef.current = null
    return undefined
  }, [status])

  // Autoscroll terminal on new lines unless user scrolled up
  // (UI-SPEC §Streaming Lifecycle — 8px sticky-bottom threshold).
  useEffect(() => {
    const el = terminalRef.current
    if (!el || userScrolledRef.current) return
    el.scrollTop = el.scrollHeight
  }, [stdoutLines.length, stderrLines.length])

  function handleTerminalScroll() {
    const el = terminalRef.current
    if (!el) return
    const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 8
    userScrolledRef.current = !atBottom
  }

  async function handleDownload(filename: string) {
    if (!executionId) return
    setDownloadingFile(filename)
    setDownloadError(null)
    try {
      const res = await apiFetch(`/code-executions/${executionId}`)
      const json = (await res.json()) as { files?: SandboxFile[] }
      const fresh = (json.files ?? []).find((f) => f.filename === filename)
      if (fresh?.signed_url) {
        window.open(fresh.signed_url, '_blank', 'noopener,noreferrer')
      } else {
        throw new Error('signed_url missing')
      }
    } catch {
      setDownloadError(filename)
      setTimeout(() => setDownloadError(null), 2000)
    } finally {
      setDownloadingFile(null)
    }
  }

  async function handleCopyCode() {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard write failed (permission denied, insecure context, etc.)
      // — silent failure is acceptable since user can still read the code.
    }
  }

  // Status icon + color (UI-SPEC §Status Indicator States).
  const statusIcon = (() => {
    switch (status) {
      case 'pending':
        return {
          Icon: Loader2,
          cls: 'text-muted-foreground motion-safe:animate-spin',
          label: t('sandbox.status.pending'),
        }
      case 'running':
        return {
          Icon: Loader2,
          cls: 'text-primary motion-safe:animate-spin',
          label: t('sandbox.status.running'),
        }
      case 'success':
        return {
          Icon: CheckCircle2,
          cls: 'text-green-500 dark:text-green-400',
          label: t('sandbox.status.success'),
        }
      case 'error':
        return {
          Icon: XCircle,
          cls: 'text-red-500 dark:text-red-400',
          label: t('sandbox.status.error'),
        }
      case 'timeout':
        return {
          Icon: Clock,
          cls: 'text-amber-500 dark:text-amber-400',
          label: t('sandbox.status.timeout'),
        }
    }
  })()

  const elapsedDisplay = (() => {
    if (status === 'pending') return null
    if (status === 'running') return formatMs(liveMs)
    if (executionMs !== undefined) return formatMs(executionMs)
    return null
  })()

  const errorPillKey = (() => {
    if (status !== 'error' || !errorType) return null
    if (errorType === 'runtime_error') return 'sandbox.error.runtime'
    if (errorType === 'timeout') return 'sandbox.error.timeout'
    if (errorType === 'oom') return 'sandbox.error.oom'
    return 'sandbox.error.unknown'
  })()

  const StatusIcon = statusIcon.Icon
  const showTerminalArea =
    stdoutLines.length > 0 ||
    stderrLines.length > 0 ||
    status === 'running' ||
    status === 'pending'

  return (
    <div className="border rounded-md text-xs my-1 bg-card">
      {/* 1. Header (always visible) */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border">
        <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium bg-primary/15 text-primary shrink-0">
          <Terminal className="h-3 w-3" />
          Python
        </span>
        <span
          className={`inline-flex items-center gap-1 ${statusIcon.cls}`}
          aria-live="polite"
        >
          <StatusIcon className="h-3.5 w-3.5 shrink-0" />
          <span className="text-xs">{statusIcon.label}</span>
        </span>
        {elapsedDisplay && (
          <span className="text-xs text-muted-foreground tabular-nums ml-1">
            {elapsedDisplay}
          </span>
        )}
        <button
          type="button"
          className="ml-auto text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
          aria-expanded={codeExpanded}
          onClick={() => setCodeExpanded((x) => !x)}
        >
          <ChevronRight
            className={`h-3 w-3 transition-transform ${
              codeExpanded ? 'rotate-90' : ''
            }`}
          />
          {codeExpanded ? t('sandbox.hideCode') : t('sandbox.showCode')}
        </button>
      </div>

      {/* 2. Code Preview (collapsible — D-P11-09) */}
      {codeExpanded && (
        <div className="relative border-b border-border bg-zinc-900 dark:bg-zinc-950 max-h-80 overflow-y-auto">
          <button
            type="button"
            className="absolute top-2 right-2 p-1 text-zinc-400 hover:text-zinc-100 transition-colors"
            onClick={handleCopyCode}
            aria-label={t('sandbox.copyCode')}
            title={copied ? t('sandbox.codeCopied') : t('sandbox.copyCode')}
          >
            <Copy className="h-3 w-3" />
          </button>
          <pre className="text-xs font-mono text-zinc-100 whitespace-pre-wrap break-all leading-relaxed p-3">
            {code}
          </pre>
        </div>
      )}

      {/* 3. Terminal Output Area */}
      {showTerminalArea && (
        <div
          ref={terminalRef}
          onScroll={handleTerminalScroll}
          role="log"
          aria-label={statusIcon.label}
          className="max-h-60 overflow-y-auto bg-zinc-900 dark:bg-zinc-950 px-3 py-2 font-mono text-xs leading-relaxed border-b border-border"
        >
          {stdoutLines.length === 0 &&
            stderrLines.length === 0 &&
            status === 'running' && (
              <span className="motion-safe:animate-pulse text-green-400">▊</span>
            )}
          {/* Lines render in stdout-then-stderr order. Strict
              arrival-order interleaving deferred for the v1 contract — most
              runs are stdout-dominant and the upstream callback in Plan 11-05
              keeps the two arrays separate. */}
          {stdoutLines.map((line, i) => (
            <div
              key={`o-${i}`}
              className="text-green-400 dark:text-green-400 whitespace-pre-wrap break-all"
            >
              {line}
            </div>
          ))}
          {stderrLines.map((line, i) => (
            <div
              key={`e-${i}`}
              className="text-red-400 dark:text-red-400 whitespace-pre-wrap break-all"
            >
              {line}
            </div>
          ))}
        </div>
      )}

      {/* 3.5. Error pill (status === 'error' with errorType) */}
      {errorPillKey && (
        <div className="flex items-center gap-2 mx-3 mt-2 mb-2 px-3 py-2 rounded-md border border-red-500/30 bg-red-500/10 dark:bg-red-500/15 text-xs text-red-700 dark:text-red-300">
          <AlertCircle className="h-3.5 w-3.5 text-red-500 shrink-0" />
          <span>{t(errorPillKey)}</span>
        </div>
      )}

      {/* 4. File Cards Footer (D-P11-06 — download-only via signed URL) */}
      {files.length > 0 && (
        <>
          <div className="text-xs font-medium text-muted-foreground px-3 pt-2 pb-1">
            {t('sandbox.filesGenerated')}
          </div>
          <div className="flex flex-col gap-1 px-3 pb-3">
            {files.map((f) => {
              const isDl = downloadingFile === f.filename
              const hadError = downloadError === f.filename
              return (
                <div
                  key={f.filename}
                  className="flex items-center gap-3 h-11 px-3 rounded-md border border-border bg-card hover:bg-muted/50 transition-colors"
                >
                  <FileDown className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className="text-sm text-foreground truncate flex-1">
                    {f.filename}
                  </span>
                  <span className="text-xs text-muted-foreground tabular-nums shrink-0">
                    {formatBytes(f.size_bytes)}
                  </span>
                  <Button
                    size="sm"
                    variant="default"
                    className="shrink-0 h-7 px-2 text-xs gap-1"
                    aria-label={`${t('sandbox.download')} ${f.filename}`}
                    onClick={() => handleDownload(f.filename)}
                    disabled={!executionId || isDl}
                  >
                    {isDl ? (
                      <Loader2 className="h-3 w-3 motion-safe:animate-spin" />
                    ) : hadError ? (
                      <AlertCircle className="h-3 w-3" />
                    ) : (
                      <Download className="h-3 w-3" />
                    )}
                    {hadError ? t('sandbox.downloadError') : t('sandbox.download')}
                  </Button>
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
