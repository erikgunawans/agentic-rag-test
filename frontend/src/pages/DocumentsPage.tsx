import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Grid3X3, List, Plus, Upload, HardDrive, FileText, Trash2, Loader2, Menu, PanelLeftClose, FolderPlus } from 'lucide-react'
import { supabase } from '@/lib/supabase'
import { apiFetch } from '@/lib/api'
import { useDocumentRealtime } from '@/hooks/useDocumentRealtime'
import { useSidebar } from '@/hooks/useSidebar'
import { FileUpload } from '@/components/documents/FileUpload'
import { FolderTree } from '@/components/documents/FolderTree'
import { FolderBreadcrumb } from '@/components/documents/FolderBreadcrumb'
import { CreateFolderDialog } from '@/components/documents/CreateFolderDialog'
import { useI18n } from '@/i18n/I18nContext'
import type { Document, DocumentFolder } from '@/lib/database.types'

type DocFilter = 'all' | 'nda' | 'kontrak' | 'kepatuhan' | 'laporan' | 'perjanjian' | 'invoice' | 'lainnya'
type StatusFilter = 'completed' | 'processing' | 'pending'
type ViewMode = 'grid' | 'list'

const TYPE_FILTERS: { value: DocFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'nda', label: 'NDA' },
  { value: 'kontrak', label: 'Kontrak' },
  { value: 'kepatuhan', label: 'Kepatuhan' },
  { value: 'laporan', label: 'Laporan' },
  { value: 'perjanjian', label: 'Perjanjian' },
  { value: 'invoice', label: 'Invoice' },
  { value: 'lainnya', label: 'Lainnya' },
]

const STATUS_FILTERS: { value: StatusFilter; label: string; color: string }[] = [
  { value: 'completed', label: 'Analyzed', color: 'bg-green-400' },
  { value: 'processing', label: 'Processing', color: 'bg-amber-400' },
  { value: 'pending', label: 'Pending', color: 'bg-gray-400' },
]

const STATUS_BADGE: Record<string, string> = {
  pending: 'bg-muted text-muted-foreground',
  processing: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  completed: 'bg-green-500/10 text-green-600 dark:text-green-400',
  failed: 'bg-red-500/10 text-red-600 dark:text-red-400',
}

const CATEGORY_BORDER_COLORS: Record<string, string> = {
  technical: 'oklch(0.60 0.15 250)',
  legal: 'oklch(0.55 0.20 280)',
  business: 'oklch(0.65 0.15 50)',
  academic: 'oklch(0.65 0.15 175)',
  personal: 'oklch(0.60 0.15 330)',
  other: 'oklch(0.40 0 0)',
}

function getFileBadge(filename: string): { label: string; className: string } {
  if (filename.endsWith('.pdf')) return { label: 'PDF', className: 'bg-red-500/15 text-red-600 dark:text-red-400' }
  if (filename.endsWith('.docx') || filename.endsWith('.doc')) return { label: 'DOC', className: 'bg-blue-500/15 text-blue-600 dark:text-blue-400' }
  if (filename.endsWith('.md')) return { label: 'MD', className: 'bg-emerald-500/15 text-emerald-400' }
  if (filename.endsWith('.csv')) return { label: 'CSV', className: 'bg-amber-500/15 text-amber-600 dark:text-amber-400' }
  if (filename.endsWith('.json')) return { label: 'JSON', className: 'bg-purple-500/15 text-purple-600 dark:text-purple-400' }
  return { label: 'TXT', className: 'bg-cyan-500/15 text-cyan-600 dark:text-cyan-400' }
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentsPage() {
  const { t } = useI18n()
  const { panelCollapsed, togglePanel } = useSidebar()
  const [documents, setDocuments] = useState<Document[]>([])
  const [userId, setUserId] = useState<string | undefined>()
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<DocFilter>('all')
  const [statusFilters, setStatusFilters] = useState<Set<StatusFilter>>(new Set(['completed', 'processing', 'pending']))
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false)
  const [folders, setFolders] = useState<DocumentFolder[]>([])
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null)
  const [createFolderOpen, setCreateFolderOpen] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUserId(data.session?.user.id)
    })
  }, [])

  const loadFolders = useCallback(async () => {
    const res = await apiFetch('/folders')
    const data: DocumentFolder[] = await res.json()
    setFolders(data)
  }, [])

  const loadDocuments = useCallback(async () => {
    const params = currentFolderId ? `?folder_id=${currentFolderId}` : ''
    const res = await apiFetch(`/documents${params}`)
    const data: Document[] = await res.json()
    setDocuments(data)
  }, [currentFolderId])

  useEffect(() => {
    loadFolders()
  }, [loadFolders])

  useEffect(() => {
    loadDocuments()
  }, [loadDocuments])

  const handleRealtimeUpdate = useCallback((updated: Document) => {
    setDocuments((prev) =>
      prev.map((d) => (d.id === updated.id ? { ...d, ...updated } : d)),
    )
  }, [])

  useDocumentRealtime(userId, handleRealtimeUpdate)

  async function handleDelete(id: string) {
    await apiFetch(`/documents/${id}`, { method: 'DELETE' })
    setDocuments((prev) => prev.filter((d) => d.id !== id))
  }

  async function handleCreateFolder(name: string) {
    await apiFetch('/folders', {
      method: 'POST',
      body: JSON.stringify({ name, parent_folder_id: currentFolderId }),
    })
    loadFolders()
  }

  async function handleDeleteFolder(folderId: string) {
    await apiFetch(`/folders/${folderId}`, { method: 'DELETE' })
    if (currentFolderId === folderId) setCurrentFolderId(null)
    loadFolders()
    loadDocuments()
  }

  async function handleToggleGlobal(folderId: string) {
    await apiFetch(`/folders/${folderId}/toggle-global`, { method: 'PATCH' })
    loadFolders()
  }

  function handleSelectFolder(folderId: string | null) {
    setCurrentFolderId(folderId)
  }

  function toggleStatus(s: StatusFilter) {
    setStatusFilters((prev) => {
      const next = new Set(prev)
      if (next.has(s)) next.delete(s)
      else next.add(s)
      return next
    })
  }

  function matchesTypeFilter(doc: Document, filter: DocFilter): boolean {
    if (filter === 'all') return true
    const name = doc.filename.toLowerCase()
    const meta = doc.status === 'completed' ? doc.metadata : null
    const tags = meta?.tags?.map((t) => t.toLowerCase()) ?? []
    const category = meta?.category?.toLowerCase() ?? ''
    const searchable = [name, category, ...tags].join(' ')
    return searchable.includes(filter)
  }

  const filtered = documents.filter((doc) => {
    if (!statusFilters.has(doc.status as StatusFilter)) return false
    if (!matchesTypeFilter(doc, typeFilter)) return false
    if (searchQuery && !doc.filename.toLowerCase().includes(searchQuery.toLowerCase())) return false
    return true
  })

  const totalSize = documents.reduce((sum, d) => sum + d.file_size, 0)

  return (
    <div className="flex h-full">
      {/* Mobile panel trigger */}
      <button
        onClick={() => setMobilePanelOpen(true)}
        className="md:hidden fixed bottom-4 right-4 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg focus-ring"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Mobile panel overlay */}
      {mobilePanelOpen && (
        <div className="md:hidden fixed inset-0 z-40">
          <div className="mobile-backdrop" onClick={() => setMobilePanelOpen(false)} />
          <div className="mobile-panel bg-background border-r border-border/50 overflow-y-auto">
            {/* Section 1: Upload */}
            <div className="p-4 space-y-4 border-b border-border/50">
              <div className="flex items-center gap-2">
                <Upload className="h-4 w-4 text-muted-foreground" />
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Upload</span>
              </div>

              <FileUpload onUploaded={loadDocuments} folderId={currentFolderId} />

              {/* Storage quota */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <HardDrive className="h-3 w-3" />
                    <span>Storage</span>
                  </div>
                  <span>{formatBytes(totalSize)} / 50 MB</span>
                </div>
                <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-primary to-[var(--gradient-accent-to)]"
                    style={{ width: `${Math.min((totalSize / (50 * 1024 * 1024)) * 100, 100)}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Section 2: Folders */}
            <div className="p-4 space-y-3 border-b border-border/50">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Folders</span>
                <button
                  onClick={() => setCreateFolderOpen(true)}
                  className="flex items-center justify-center h-6 w-6 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                  title="New folder"
                >
                  <FolderPlus className="h-3.5 w-3.5" />
                </button>
              </div>
              <FolderTree
                folders={folders}
                currentFolderId={currentFolderId}
                currentUserId={userId ?? null}
                onSelectFolder={handleSelectFolder}
                onDeleteFolder={handleDeleteFolder}
                onToggleGlobal={handleToggleGlobal}
              />
            </div>

            {/* Section 3: Filter */}
            <div className="p-4 space-y-4">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Filter</span>

              {/* Type filters */}
              <div className="space-y-1">
                {TYPE_FILTERS.map(({ value, label }) => {
                  const count = value === 'all' ? documents.length : documents.filter((d) => matchesTypeFilter(d, value)).length
                  return (
                    <button
                      key={value}
                      onClick={() => setTypeFilter(value)}
                      className={`flex w-full items-center justify-between rounded-md focus-ring px-2.5 py-1.5 text-xs transition-colors ${
                        typeFilter === value ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                      }`}
                    >
                      <span>{label}</span>
                      <span className="text-[10px] tabular-nums">{count}</span>
                    </button>
                  )
                })}
              </div>

              {/* Status checkboxes */}
              <div className="space-y-2 pt-2 border-t border-border/50">
                <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Status</span>
                {STATUS_FILTERS.map(({ value, label, color }) => (
                  <button
                    key={value}
                    onClick={() => toggleStatus(value)}
                    className="flex w-full items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors focus-ring"
                  >
                    <div className={`h-3.5 w-3.5 rounded border flex items-center justify-center ${
                      statusFilters.has(value) ? 'border-primary bg-primary' : 'border-border'
                    }`}>
                      {statusFilters.has(value) && <span className="text-[8px] text-primary-foreground">&#10003;</span>}
                    </div>
                    <span className={`h-2 w-2 rounded-full ${color}`} />
                    <span>{label}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Column 2 — Sidebar panel (300px) */}
      {!panelCollapsed && (
      <div className="hidden md:flex w-[340px] shrink-0 flex-col border-r border-border/50 bg-sidebar overflow-y-auto">
        {/* Section 1: Upload */}
        <div className="p-4 space-y-4 border-b border-border/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Upload className="h-4 w-4 text-muted-foreground" />
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Upload</span>
            </div>
            <button onClick={togglePanel} className="flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors focus-ring" title="Collapse sidebar">
              <PanelLeftClose className="h-4 w-4" />
            </button>
          </div>

          <FileUpload onUploaded={loadDocuments} folderId={currentFolderId} />

          {/* Storage quota */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[10px] text-muted-foreground">
              <div className="flex items-center gap-1">
                <HardDrive className="h-3 w-3" />
                <span>Storage</span>
              </div>
              <span>{formatBytes(totalSize)} / 50 MB</span>
            </div>
            <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-primary to-[var(--gradient-accent-to)]"
                style={{ width: `${Math.min((totalSize / (50 * 1024 * 1024)) * 100, 100)}%` }}
              />
            </div>
          </div>
        </div>

        {/* Section 2: Folders */}
        <div className="p-4 space-y-3 border-b border-border/50">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Folders</span>
            <button
              onClick={() => setCreateFolderOpen(true)}
              className="flex items-center justify-center h-6 w-6 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              title="New folder"
            >
              <FolderPlus className="h-3.5 w-3.5" />
            </button>
          </div>
          <FolderTree
            folders={folders}
            currentFolderId={currentFolderId}
            currentUserId={userId ?? null}
            onSelectFolder={handleSelectFolder}
            onDeleteFolder={handleDeleteFolder}
            onToggleGlobal={handleToggleGlobal}
          />
        </div>

        {/* Section 3: Filter */}
        <div className="p-4 space-y-4">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Filter</span>

          {/* Type filters */}
          <div className="space-y-1">
            {TYPE_FILTERS.map(({ value, label }) => {
              const count = value === 'all' ? documents.length : documents.filter((d) => matchesTypeFilter(d, value)).length
              return (
                <button
                  key={value}
                  onClick={() => setTypeFilter(value)}
                  className={`flex w-full items-center justify-between rounded-md focus-ring px-2.5 py-1.5 text-xs transition-colors ${
                    typeFilter === value ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                  }`}
                >
                  <span>{label}</span>
                  <span className="text-[10px] tabular-nums">{count}</span>
                </button>
              )
            })}
          </div>

          {/* Status checkboxes */}
          <div className="space-y-2 pt-2 border-t border-border/50">
            <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Status</span>
            {STATUS_FILTERS.map(({ value, label, color }) => (
              <button
                key={value}
                onClick={() => toggleStatus(value)}
                className="flex w-full items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors focus-ring"
              >
                <div className={`h-3.5 w-3.5 rounded border flex items-center justify-center ${
                  statusFilters.has(value) ? 'border-primary bg-primary' : 'border-border'
                }`}>
                  {statusFilters.has(value) && <span className="text-[8px] text-primary-foreground">&#10003;</span>}
                </div>
                <span className={`h-2 w-2 rounded-full ${color}`} />
                <span>{label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
      )}

      {/* Column 3 — Main document area */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* Breadcrumb */}
        {currentFolderId && (
          <FolderBreadcrumb
            folders={folders}
            currentFolderId={currentFolderId}
            onNavigate={handleSelectFolder}
          />
        )}

        {/* Header — inline with content */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <h1 className="text-lg tracking-tight">{t('documents.title')}</h1>
            <span className="text-xs text-muted-foreground">{filtered.length} documents</span>
          </div>
          <div className="flex items-center gap-2">
            {/* Search */}
            <div className="flex items-center gap-2 rounded-lg border border-border/50 bg-secondary/50 px-2.5 py-1.5 w-48">
              <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <input
                type="text"
                placeholder="Search..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-transparent text-xs text-foreground placeholder:text-muted-foreground focus:outline-none"
              />
            </div>
            {/* View toggle */}
            <div className="flex rounded-lg border border-border/50">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-2 transition-colors ${viewMode === 'grid' ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'}`}
              >
                <Grid3X3 className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-2 transition-colors ${viewMode === 'list' ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'}`}
              >
                <List className="h-3.5 w-3.5" />
              </button>
            </div>
            {/* New Document button */}
            <Link to="/create" className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:opacity-90 transition-opacity">
              <Plus className="h-3.5 w-3.5" />
              New Document
            </Link>
          </div>
        </div>

        {/* Document grid/list */}
        <div>
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <FileText className="h-12 w-12 text-muted-foreground mb-3" />
              <p className="text-sm text-muted-foreground">{t('docList.empty')}</p>
            </div>
          ) : (
            <div className={viewMode === 'grid' ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4' : 'space-y-2'}>
              {filtered.map((doc) => {
                const meta = doc.status === 'completed' ? doc.metadata : null
                const tags = meta?.tags?.slice(0, 2) ?? []
                return (
                  <div
                    key={doc.id}
                    className={`group rounded-xl border p-4 transition-all duration-200 hover:shadow-[var(--shadow-sm)] hover:border-border/80 cursor-pointer interactive-lift ${
                      viewMode === 'list' ? 'flex items-center gap-4' : 'space-y-3'
                    }`}
                    style={{
                      borderLeftWidth: meta?.category ? '3px' : undefined,
                      borderLeftColor: meta?.category ? (CATEGORY_BORDER_COLORS[meta.category] ?? undefined) : undefined,
                    }}
                  >
                    {/* File type badge + menu */}
                    <div className="flex items-center justify-between">
                      <div className={`flex h-8 w-8 items-center justify-center rounded-lg text-[9px] font-bold ${getFileBadge(doc.filename).className}`}>
                        {getFileBadge(doc.filename).label}
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(doc.id) }}
                        className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-all"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>

                    {/* Title */}
                    <div className={viewMode === 'list' ? 'flex-1 min-w-0' : ''}>
                      <p className="text-sm font-medium truncate">{doc.filename}</p>
                      {meta?.category && (
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: CATEGORY_BORDER_COLORS[meta.category] }} />
                          <span className="text-[10px] font-medium" style={{ color: CATEGORY_BORDER_COLORS[meta.category] }}>
                            {meta.category}
                          </span>
                        </div>
                      )}
                      {meta?.summary && viewMode === 'grid' && (
                        <p className="text-[10px] text-muted-foreground line-clamp-2 mt-1">{meta.summary}</p>
                      )}
                    </div>

                    {/* Footer */}
                    <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <span>{formatBytes(doc.file_size)}</span>
                        {doc.chunk_count != null && <span>· {doc.chunk_count} chunks</span>}
                      </div>
                      <div className="flex items-center gap-1.5">
                        {tags.map((tag) => (
                          <span key={tag} className="rounded-full bg-muted px-1.5 py-0.5 text-[8px]">{tag}</span>
                        ))}
                        <span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-medium ${STATUS_BADGE[doc.status]}`}>
                          {doc.status === 'processing' && <Loader2 className="h-2.5 w-2.5 animate-spin" />}
                          {doc.status}
                        </span>
                      </div>
                    </div>
                  </div>
                )
              })}

              {/* Ghost upload card */}
              {viewMode === 'grid' && (
                <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-border p-4 cursor-pointer hover:border-primary/50 hover:shadow-[var(--glow-sm)] transition-all min-h-[160px]">
                  <Plus className="h-6 w-6 text-muted-foreground mb-2" />
                  <span className="text-xs text-muted-foreground">Upload New</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Create folder dialog */}
      <CreateFolderDialog
        open={createFolderOpen}
        onClose={() => setCreateFolderOpen(false)}
        onCreate={handleCreateFolder}
      />
    </div>
  )
}
