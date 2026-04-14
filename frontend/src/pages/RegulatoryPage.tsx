import { useState, useEffect, useCallback } from 'react'
import { BookOpen, Plus, Search, Menu, ChevronLeft, PanelLeftClose, Loader2 } from 'lucide-react'
import { useSidebar } from '@/hooks/useSidebar'

import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { apiFetch } from '@/lib/api'
import { formatTimeAgo } from '@/hooks/useToolHistory'

interface RegulatoryUpdate {
  id: string
  title: string
  source_name: string
  relevance_score: number
  regulation_number: string
  published_at: string
  crawled_at: string
  is_read: boolean
}

interface RegulatorySource {
  id: string
  name: string
  source_type: string
  status: string
}

const RELEVANCE_STYLE: Record<string, { color: string; bg: string; label: string }> = {
  high: { color: 'text-red-400', bg: 'bg-red-500/10', label: 'HIGH' },
  medium: { color: 'text-amber-400', bg: 'bg-amber-500/10', label: 'MEDIUM' },
  low: { color: 'text-green-400', bg: 'bg-green-500/10', label: 'LOW' },
}

const SOURCE_TYPES = ['all', 'jdih', 'idx', 'ojk', 'perda', 'custom']

const STATUS_BADGE: Record<string, { color: string; bg: string }> = {
  active: { color: 'text-green-400', bg: 'bg-green-500/15' },
  inactive: { color: 'text-muted-foreground', bg: 'bg-secondary' },
  error: { color: 'text-red-400', bg: 'bg-red-500/15' },
}

const inputBase = "w-full rounded-lg bg-secondary text-foreground px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
const inputClass = `${inputBase} border border-border`

function getRelevanceLevel(score: number): string {
  if (score >= 0.7) return 'high'
  if (score >= 0.4) return 'medium'
  return 'low'
}

export function RegulatoryPage() {
  const { isAdmin } = useAuth()
  const { panelCollapsed, togglePanel } = useSidebar()
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false)

  const [updates, setUpdates] = useState<RegulatoryUpdate[]>([])
  const [sources, setSources] = useState<RegulatorySource[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [sourceTypeFilter, setSourceTypeFilter] = useState('all')

  const fetchUpdates = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (search) params.set('search', search)
      if (sourceTypeFilter !== 'all') params.set('source_type', sourceTypeFilter)
      const res = await apiFetch(`/regulatory/updates?${params}`)
      const data = await res.json()
      setUpdates(data.data || [])
    } catch {
      setUpdates([])
    } finally {
      setLoading(false)
    }
  }, [search, sourceTypeFilter])

  const fetchSources = useCallback(async () => {
    try {
      const res = await apiFetch('/regulatory/sources')
      const data = await res.json()
      setSources(data.data || [])
    } catch {
      setSources([])
    }
  }, [])

  useEffect(() => {
    const timer = setTimeout(fetchUpdates, 300)
    return () => clearTimeout(timer)
  }, [fetchUpdates])

  useEffect(() => {
    fetchSources()
  }, [fetchSources])

  async function markAsRead(id: string) {
    try {
      await apiFetch(`/regulatory/updates/${id}/read`, { method: 'PATCH' })
      setUpdates(prev => prev.map(u => u.id === id ? { ...u, is_read: true } : u))
    } catch {
      // silent
    }
  }

  function renderPanel() {
    return (
      <div className="px-5 py-4 space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
          <input
            className={`${inputClass} pl-8`}
            placeholder="Search regulations..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label="Search regulations"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-[10px] font-medium">Source Type</label>
          <select className={inputClass} value={sourceTypeFilter} onChange={e => setSourceTypeFilter(e.target.value)} aria-label="Filter by source type">
            {SOURCE_TYPES.map(st => (
              <option key={st} value={st}>{st === 'all' ? 'All Sources' : st.toUpperCase()}</option>
            ))}
          </select>
        </div>

        {isAdmin && (
          <div className="pt-3 border-t border-border/50 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-[10px] font-semibold uppercase text-muted-foreground">Sources</h3>
              <Button size="sm" variant="outline" className="text-[10px] h-6 px-2 gap-1">
                <Plus className="h-3 w-3" /> Add Source
              </Button>
            </div>
            {sources.length === 0 ? (
              <p className="text-[10px] text-muted-foreground">No sources configured</p>
            ) : (
              <div className="space-y-1.5">
                {sources.map(source => {
                  const badge = STATUS_BADGE[source.status] || STATUS_BADGE.inactive
                  return (
                    <div key={source.id} className="flex items-center justify-between rounded-md border border-border/50 px-3 py-2">
                      <span className="text-xs font-medium truncate">{source.name}</span>
                      <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded-full ${badge.bg} ${badge.color}`}>
                        {source.status}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="flex h-full">
      {/* Mobile FAB */}
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
            <div className="flex items-center justify-between px-5 py-3 border-b border-border/50">
              <div>
                <h1 className="text-sm font-semibold">Regulatory Intelligence</h1>
              </div>
              <button onClick={() => setMobilePanelOpen(false)} className="text-muted-foreground hover:text-foreground focus-ring">
                <ChevronLeft className="h-4 w-4" />
              </button>
            </div>
            {renderPanel()}
          </div>
        </div>
      )}

      {/* Desktop filter panel */}
      {!panelCollapsed && (
        <div className="hidden md:flex w-[340px] shrink-0 flex-col border-r border-border/50 glass">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border/50">
            <div>
              <h1 className="text-sm font-semibold">Regulatory Intelligence</h1>
              <p className="text-[10px] text-muted-foreground">{updates.length} updates</p>
            </div>
            <button onClick={togglePanel} className="flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors focus-ring">
              <PanelLeftClose className="h-4 w-4" />
            </button>
          </div>
          {renderPanel()}
        </div>
      )}

      {/* Main content — regulatory update cards */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : updates.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64">
            <BookOpen className="h-10 w-10 text-muted-foreground/40 mb-3" />
            <p className="text-sm text-muted-foreground">No regulatory updates found</p>
          </div>
        ) : (
          <div className="space-y-3 max-w-[900px]">
            {updates.map(update => {
              const level = getRelevanceLevel(update.relevance_score)
              const relevance = RELEVANCE_STYLE[level]
              return (
                <button
                  key={update.id}
                  onClick={() => markAsRead(update.id)}
                  aria-label={`${update.is_read ? '' : 'Mark as read: '}${update.title}`}
                  className={`w-full text-left rounded-lg border p-4 space-y-2 transition-colors hover:bg-accent/30 ${
                    !update.is_read ? 'border-l-4 border-l-primary border-t-border/50 border-r-border/50 border-b-border/50' : 'border-border/50'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <h3 className={`text-xs font-semibold ${!update.is_read ? 'text-foreground' : 'text-muted-foreground'}`}>
                        {update.title}
                      </h3>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                          {update.source_name}
                        </span>
                        <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded ${relevance.bg} ${relevance.color}`}>
                          {relevance.label}
                        </span>
                        {update.regulation_number && (
                          <span className="text-[9px] text-muted-foreground">
                            {update.regulation_number}
                          </span>
                        )}
                      </div>
                    </div>
                    {!update.is_read && (
                      <div className="h-2 w-2 shrink-0 rounded-full bg-primary mt-1" />
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-[9px] text-muted-foreground">
                    <span>Published {formatTimeAgo(update.published_at)}</span>
                    <span>Crawled {formatTimeAgo(update.crawled_at)}</span>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
