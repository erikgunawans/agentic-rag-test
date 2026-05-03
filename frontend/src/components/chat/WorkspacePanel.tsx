/**
 * Phase 18 — WS-07, WS-08, WS-11.
 *
 * WorkspacePanel — persistent sidebar panel that shows the virtual workspace
 * file list for the active thread.
 *
 * Visibility rule (WS-11): panel is rendered only when files.length > 0.
 * Decoupled from Deep Mode — visible for ANY thread that has workspace files.
 *
 * Features:
 *   - File list with path, size (formatBytes), source badge, relative time
 *   - Clicking a text file opens an inline expanded view (content fetched from
 *     GET /threads/{id}/files/{path}, cached in component state)
 *   - Clicking a binary file navigates to the GET endpoint; the browser follows
 *     the 307 redirect to the signed URL triggering a download
 *   - Collapsible via chevron button
 *
 * Security (T-18-25): file content rendered as React text children inside
 * a <pre> element. React auto-escapes string children — no HTML injection.
 *
 * CLAUDE.md rule: persistent panel — NO backdrop-blur, NO glass. Solid bg-card.
 */

import { useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Download,
  FileText,
  File as FileIcon,
  Image as ImageIcon,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n/I18nContext'
import { apiFetch } from '@/lib/api'
import type { WorkspaceFile } from '@/hooks/useChatState'

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

/** Format a byte count into a human-readable string. */
export function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * Return true when a file should be opened inline (text preview).
 * Unknown MIME (null) is treated as text — server defaults to text/plain for
 * unrecognised types.
 */
function isTextFile(mime: string | null): boolean {
  if (!mime) return true
  return mime.startsWith('text/') || mime === 'application/json'
}

/** Pick the appropriate Lucide icon component based on MIME type. */
function fileIconFor(mime: string | null) {
  if (mime?.startsWith('image/')) return ImageIcon
  if (mime?.startsWith('text/') || mime === 'application/json') return FileText
  return FileIcon
}

/** Convert an ISO timestamp to a compact relative-time string. */
function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diffMs / 60_000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return new Date(iso).toLocaleDateString()
}

// ---------------------------------------------------------------------------
// SourceBadge sub-component
// ---------------------------------------------------------------------------

const SOURCE_COLORS: Record<WorkspaceFile['source'], string> = {
  agent: 'bg-purple-500/20 text-purple-300',
  sandbox: 'bg-blue-500/20 text-blue-300',
  upload: 'bg-zinc-500/20 text-zinc-300',
}

function SourceBadge({ source }: { source: WorkspaceFile['source'] }) {
  const { t } = useI18n()
  return (
    <span
      className={`px-1.5 py-0.5 rounded text-xs ${SOURCE_COLORS[source]}`}
      data-testid={`source-badge-${source}`}
    >
      {t(`workspace.source.${source}`)}
    </span>
  )
}

// ---------------------------------------------------------------------------
// WorkspacePanel props
// ---------------------------------------------------------------------------

interface WorkspacePanelProps {
  threadId: string
  files: WorkspaceFile[]
}

// ---------------------------------------------------------------------------
// WorkspacePanel
// ---------------------------------------------------------------------------

export function WorkspacePanel({ threadId, files }: WorkspacePanelProps) {
  const { t } = useI18n()
  const [collapsed, setCollapsed] = useState(false)
  const [expandedPath, setExpandedPath] = useState<string | null>(null)
  const [contentCache, setContentCache] = useState<Record<string, string>>({})
  const [loadingPath, setLoadingPath] = useState<string | null>(null)

  // WS-11: panel is hidden when the thread has no workspace files.
  if (files.length === 0) return null

  const handleClick = async (f: WorkspaceFile) => {
    if (isTextFile(f.mime_type)) {
      // Toggle inline view
      if (expandedPath === f.file_path) {
        setExpandedPath(null)
        return
      }
      if (!contentCache[f.file_path]) {
        setLoadingPath(f.file_path)
        try {
          const res = await apiFetch(
            `/threads/${threadId}/files/${encodeURIComponent(f.file_path)}`,
          )
          const text = await res.text()
          setContentCache((c) => ({ ...c, [f.file_path]: text }))
        } catch {
          setContentCache((c) => ({ ...c, [f.file_path]: '(failed to load)' }))
        } finally {
          setLoadingPath(null)
        }
      }
      setExpandedPath(f.file_path)
    } else {
      // Binary: navigate to GET endpoint; browser follows 307 to signed URL.
      window.open(
        `/threads/${threadId}/files/${encodeURIComponent(f.file_path)}`,
        '_blank',
        'noopener,noreferrer',
      )
    }
  }

  return (
    <aside
      // Phase 18 / CLAUDE.md: persistent panel — NO backdrop-blur.
      // Solid bg-card surface only.
      className="flex flex-col w-72 shrink-0 border-l border-border/50 bg-background"
      data-testid="workspace-panel"
      aria-label={t('workspace.title')}
    >
      {/* Header with collapse toggle */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
        <h3 className="text-sm font-semibold text-foreground">
          {t('workspace.title')}{' '}
          <span className="text-muted-foreground font-normal">({files.length})</span>
        </h3>
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? t('workspace.expand') : t('workspace.collapse')}
          className="flex h-6 w-6 items-center justify-center rounded hover:bg-accent transition-colors text-muted-foreground"
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {/* File list — hidden when collapsed */}
      {!collapsed && (
        <div className="flex-1 overflow-y-auto px-3 py-2">
          {files.length === 0 ? (
            <p className="text-sm text-muted-foreground px-1">{t('workspace.empty')}</p>
          ) : (
            <ul className="space-y-1">
              {files.map((f) => {
                const Icon = fileIconFor(f.mime_type)
                const isExpanded = expandedPath === f.file_path
                const isText = isTextFile(f.mime_type)
                const isLoading = loadingPath === f.file_path

                return (
                  <li key={f.file_path}>
                    <button
                      type="button"
                      onClick={() => handleClick(f)}
                      disabled={isLoading}
                      className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-accent/50 text-left transition-colors disabled:opacity-60"
                      data-testid={`workspace-file-${f.file_path}`}
                    >
                      <Icon size={14} className="text-muted-foreground shrink-0" />
                      <span className="flex-1 text-sm truncate text-foreground">
                        {f.file_path}
                      </span>
                      <span className="text-xs text-muted-foreground tabular-nums shrink-0">
                        {formatBytes(f.size_bytes)}
                      </span>
                      <SourceBadge source={f.source} />
                      <span className="text-xs text-muted-foreground/60 shrink-0">
                        {relativeTime(f.updated_at)}
                      </span>
                      {!isText && (
                        <Download size={12} className="text-muted-foreground shrink-0" />
                      )}
                    </button>

                    {/* Inline text view — T-18-25: React text-children auto-escape */}
                    {isExpanded && isText && (
                      <pre
                        className="mt-1 p-2 bg-zinc-900 rounded text-xs whitespace-pre-wrap max-h-96 overflow-auto text-zinc-100"
                        data-testid={`workspace-content-${f.file_path}`}
                      >
                        {contentCache[f.file_path] ?? '...'}
                      </pre>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      )}
    </aside>
  )
}
