import { useState, useEffect, useCallback } from 'react'
import { CheckCircle, XCircle, RotateCcw, FileCheck, Menu, ChevronLeft, PanelLeftClose, Inbox } from 'lucide-react'
import { useSidebar } from '@/hooks/useSidebar'
import { useI18n } from '@/i18n/I18nContext'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { apiFetch } from '@/lib/api'
import { formatTimeAgo } from '@/hooks/useToolHistory'

interface ApprovalRequest {
  id: string
  user_id: string
  title: string
  resource_type: string
  resource_id: string
  status: 'pending' | 'in_progress' | 'approved' | 'rejected' | 'cancelled'
  current_step: number
  submitted_at: string
  completed_at: string | null
}

const STATUS_STYLE: Record<string, { color: string; bg: string; label: string }> = {
  pending: { color: 'text-amber-400', bg: 'border-amber-500/30 bg-amber-500/5', label: 'PENDING' },
  in_progress: { color: 'text-blue-400', bg: 'border-blue-500/30 bg-blue-500/5', label: 'IN PROGRESS' },
  approved: { color: 'text-green-400', bg: 'border-green-500/30 bg-green-500/5', label: 'APPROVED' },
  rejected: { color: 'text-red-400', bg: 'border-red-500/30 bg-red-500/5', label: 'REJECTED' },
  cancelled: { color: 'text-gray-400', bg: 'border-gray-500/30 bg-gray-500/5', label: 'CANCELLED' },
}

export function ApprovalInboxPage() {
  const { t } = useI18n()
  const { panelCollapsed, togglePanel } = useSidebar()
  const { user, isAdmin } = useAuth()
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false)

  const [inboxItems, setInboxItems] = useState<ApprovalRequest[]>([])
  const [myRequests, setMyRequests] = useState<ApprovalRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [section, setSection] = useState<'inbox' | 'my-requests'>(isAdmin ? 'inbox' : 'my-requests')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [actingOn, setActingOn] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [myRes, inboxRes] = await Promise.all([
        apiFetch('/approvals/my-requests'),
        isAdmin ? apiFetch('/approvals/inbox') : Promise.resolve(null),
      ])
      const myData = await myRes.json()
      setMyRequests(myData.data || myData || [])
      if (inboxRes) {
        const inboxData = await inboxRes.json()
        setInboxItems(inboxData.data || inboxData || [])
      }
    } catch {
      setMyRequests([])
      setInboxItems([])
    } finally {
      setLoading(false)
    }
  }, [isAdmin])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const items = section === 'inbox' ? inboxItems : myRequests
  const filtered = statusFilter
    ? items.filter(r => r.status === statusFilter)
    : items

  const counts = items.reduce<Record<string, number>>((acc, r) => {
    acc[r.status] = (acc[r.status] || 0) + 1
    return acc
  }, {})

  async function handleAction(id: string, action: 'approve' | 'reject' | 'return' | 'cancel') {
    setActingOn(id)
    try {
      if (action === 'cancel') {
        await apiFetch(`/approvals/${id}/cancel`, { method: 'POST' })
      } else {
        await apiFetch(`/approvals/${id}/action`, {
          method: 'POST',
          body: JSON.stringify({ action, comments: '' }),
        })
      }
      await fetchData()
    } catch {
      // silent
    } finally {
      setActingOn(null)
    }
  }

  const statusFilters = ['', 'pending', 'approved', 'rejected']

  function renderPanel() {
    return (
      <div className="px-5 py-4 space-y-4">
        {/* Section toggle */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            {t('approvals.section') || 'Section'}
          </label>
          <div className="flex flex-col gap-1.5">
            {isAdmin && (
              <button
                onClick={() => setSection('inbox')}
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                  section === 'inbox'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-secondary text-muted-foreground hover:text-foreground'
                }`}
              >
                <Inbox className="h-3.5 w-3.5" />
                {t('approvals.inbox') || 'Inbox'}
                {inboxItems.length > 0 && (
                  <span className="ml-auto text-[10px] rounded-full bg-background/20 px-1.5 py-0.5">
                    {inboxItems.length}
                  </span>
                )}
              </button>
            )}
            <button
              onClick={() => setSection('my-requests')}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                section === 'my-requests'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-muted-foreground hover:text-foreground'
              }`}
            >
              <FileCheck className="h-3.5 w-3.5" />
              {t('approvals.myRequests') || 'My Requests'}
              {myRequests.length > 0 && (
                <span className="ml-auto text-[10px] rounded-full bg-background/20 px-1.5 py-0.5">
                  {myRequests.length}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Status filters */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            {t('approvals.filterStatus') || 'Filter by Status'}
          </label>
          <div className="flex flex-col gap-1.5">
            {statusFilters.map(s => {
              const label = s
                ? (t(`approvals.status.${s}`) || STATUS_STYLE[s]?.label || s)
                : (t('approvals.all') || 'All')
              const count = s ? (counts[s] || 0) : items.length
              return (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={`flex items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                    statusFilter === s
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <span>{label}</span>
                  <span className="text-[10px] rounded-full bg-background/20 px-1.5 py-0.5">{count}</span>
                </button>
              )
            })}
          </div>
        </div>
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
                <h1 className="text-sm font-semibold">{t('approvals.title') || 'Approvals'}</h1>
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
        <div className="hidden md:flex w-[340px] shrink-0 flex-col border-r border-border/50">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border/50">
            <div>
              <h1 className="text-sm font-semibold">{t('approvals.title') || 'Approvals'}</h1>
              <p className="text-[10px] text-muted-foreground">
                {filtered.length} {t('approvals.items') || 'items'}
              </p>
            </div>
            <button onClick={togglePanel} className="flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors focus-ring">
              <PanelLeftClose className="h-4 w-4" />
            </button>
          </div>
          {renderPanel()}
        </div>
      )}

      {/* Main content — approval request cards */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <p className="text-xs text-muted-foreground">{t('approvals.loading') || 'Loading...'}</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64">
            <Inbox className="h-10 w-10 text-muted-foreground/40 mb-3" />
            <p className="text-sm text-muted-foreground">{t('approvals.empty') || 'No approval requests'}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 max-w-[900px]">
            {filtered.map(request => {
              const style = STATUS_STYLE[request.status] || STATUS_STYLE.pending
              const isOwn = request.user_id === user?.id
              return (
                <div key={request.id} className={`rounded-lg border p-4 space-y-2.5 ${style.bg}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-xs font-semibold truncate">{request.title}</h3>
                      <div className="flex items-center gap-1.5 mt-1">
                        <span className={`text-[9px] font-bold uppercase ${style.color}`}>
                          {style.label}
                        </span>
                        <span className="text-[9px] text-muted-foreground">
                          {request.resource_type}
                        </span>
                      </div>
                    </div>
                    <span className="text-[9px] text-muted-foreground whitespace-nowrap shrink-0">
                      {formatTimeAgo(request.submitted_at)}
                    </span>
                  </div>

                  {request.completed_at && (
                    <p className="text-[10px] text-muted-foreground">
                      {t('approvals.completedAt') || 'Completed'}: {formatTimeAgo(request.completed_at)}
                    </p>
                  )}

                  {/* Admin actions on inbox pending items */}
                  {section === 'inbox' && isAdmin && request.status === 'pending' && (
                    <div className="flex gap-1.5 pt-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-[10px] h-6 px-2 text-green-400 hover:text-green-300 hover:bg-green-500/10"
                        disabled={actingOn === request.id}
                        onClick={() => handleAction(request.id, 'approve')}
                      >
                        <CheckCircle className="h-3 w-3 mr-1" />
                        {t('approvals.approve') || 'Approve'}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-[10px] h-6 px-2 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                        disabled={actingOn === request.id}
                        onClick={() => handleAction(request.id, 'reject')}
                      >
                        <XCircle className="h-3 w-3 mr-1" />
                        {t('approvals.reject') || 'Reject'}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-[10px] h-6 px-2 text-amber-400 hover:text-amber-300 hover:bg-amber-500/10"
                        disabled={actingOn === request.id}
                        onClick={() => handleAction(request.id, 'return')}
                      >
                        <RotateCcw className="h-3 w-3 mr-1" />
                        {t('approvals.return') || 'Return'}
                      </Button>
                    </div>
                  )}

                  {/* Cancel button for user's own pending requests */}
                  {section === 'my-requests' && isOwn && request.status === 'pending' && (
                    <div className="flex gap-1.5 pt-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-[10px] h-6 px-2 text-gray-400 hover:text-gray-300 hover:bg-gray-500/10"
                        disabled={actingOn === request.id}
                        onClick={() => handleAction(request.id, 'cancel')}
                      >
                        <XCircle className="h-3 w-3 mr-1" />
                        {t('approvals.cancel') || 'Cancel'}
                      </Button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
