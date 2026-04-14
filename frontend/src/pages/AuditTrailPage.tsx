import { useCallback, useEffect, useState } from 'react'
import { FileText, Download, Filter } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n/I18nContext'

interface AuditLogEntry {
  id: string
  user_id: string | null
  user_email: string | null
  action: string
  resource_type: string
  resource_id: string | null
  details: Record<string, unknown>
  ip_address: string | null
  created_at: string
}

export function AuditTrailPage() {
  const { t } = useI18n()
  const [logs, setLogs] = useState<AuditLogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionFilter, setActionFilter] = useState('')
  const [resourceFilter, setResourceFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [actions, setActions] = useState<string[]>([])
  const [offset, setOffset] = useState(0)
  const limit = 50

  const inputClass = 'w-full rounded-md border bg-secondary text-foreground px-3 py-2 text-sm'

  const loadLogs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (actionFilter) params.set('action', actionFilter)
      if (resourceFilter) params.set('resource_type', resourceFilter)
      if (dateFrom) params.set('date_from', dateFrom)
      if (dateTo) params.set('date_to', dateTo)
      params.set('limit', String(limit))
      params.set('offset', String(offset))

      const res = await apiFetch(`/admin/audit-logs?${params}`)
      const data = await res.json()
      setLogs(data.data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('audit.error.load'))
    } finally {
      setLoading(false)
    }
  }, [actionFilter, resourceFilter, dateFrom, dateTo, offset, t])

  const loadActions = useCallback(async () => {
    try {
      const res = await apiFetch('/admin/audit-logs/actions')
      const data = await res.json()
      setActions(data.actions)
    } catch {
      // Silently fail — filter still works with text input
    }
  }, [])

  useEffect(() => { loadLogs() }, [loadLogs])
  useEffect(() => { loadActions() }, [loadActions])

  async function handleExport() {
    try {
      const params = new URLSearchParams()
      if (actionFilter) params.set('action', actionFilter)
      if (resourceFilter) params.set('resource_type', resourceFilter)
      if (dateFrom) params.set('date_from', dateFrom)
      if (dateTo) params.set('date_to', dateTo)

      const res = await apiFetch(`/admin/audit-logs/export?${params}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'audit-logs.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('audit.error.load'))
    }
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleString('id-ID', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  }

  const actionBadgeColor: Record<string, string> = {
    upload: 'bg-blue-500/15 text-blue-400',
    delete: 'bg-red-500/15 text-red-400',
    create: 'bg-green-500/15 text-green-400',
    update: 'bg-amber-500/15 text-amber-400',
    compliance: 'bg-emerald-500/15 text-emerald-400',
    analyze: 'bg-purple-500/15 text-purple-400',
    compare: 'bg-cyan-500/15 text-cyan-400',
  }

  return (
    <div className="flex-1 overflow-auto p-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <FileText className="h-5 w-5 text-amber-400" />
        <h1 className="text-lg font-semibold">{t('audit.title')}</h1>
        <span className="rounded-full bg-amber-500/15 px-2.5 py-0.5 text-xs font-medium text-amber-400">
          {t('admin.badge')}
        </span>
        <div className="flex-1" />
        <Button
          onClick={handleExport}
          variant="outline"
          size="sm"
          className="gap-1.5"
        >
          <Download className="h-3.5 w-3.5" />
          {t('audit.export')}
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="flex items-center gap-1.5">
          <Filter className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">{t('audit.filters')}</span>
        </div>
        <select
          value={actionFilter}
          onChange={e => { setActionFilter(e.target.value); setOffset(0) }}
          className={`${inputClass} max-w-[160px]`}
        >
          <option value="">{t('audit.filter.allActions')}</option>
          {actions.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <input
          type="text"
          value={resourceFilter}
          onChange={e => { setResourceFilter(e.target.value); setOffset(0) }}
          placeholder={t('audit.filter.resourceType')}
          className={`${inputClass} max-w-[160px]`}
        />
        <input
          type="date"
          value={dateFrom}
          onChange={e => { setDateFrom(e.target.value); setOffset(0) }}
          className={`${inputClass} max-w-[150px]`}
        />
        <span className="text-xs text-muted-foreground">&mdash;</span>
        <input
          type="date"
          value={dateTo}
          onChange={e => { setDateTo(e.target.value); setOffset(0) }}
          className={`${inputClass} max-w-[150px]`}
        />
      </div>

      {/* Table */}
      <div>
        {error && (
          <div className="mb-4 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <FileText className="h-10 w-10 mb-3 opacity-40" />
            <p className="text-sm">{t('audit.empty')}</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/50 text-left text-xs text-muted-foreground">
                <th className="pb-2 pr-4 font-medium">{t('audit.col.timestamp')}</th>
                <th className="pb-2 pr-4 font-medium">{t('audit.col.user')}</th>
                <th className="pb-2 pr-4 font-medium">{t('audit.col.action')}</th>
                <th className="pb-2 pr-4 font-medium">{t('audit.col.resource')}</th>
                <th className="pb-2 font-medium">{t('audit.col.details')}</th>
              </tr>
            </thead>
            <tbody>
              {logs.map(log => (
                <tr key={log.id} className="border-b border-border/20 hover:bg-accent/30 transition-colors">
                  <td className="py-2.5 pr-4 text-xs text-muted-foreground whitespace-nowrap">
                    {formatDate(log.created_at)}
                  </td>
                  <td className="py-2.5 pr-4 text-xs">
                    {log.user_email || '\u2014'}
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${actionBadgeColor[log.action] || 'bg-secondary text-foreground'}`}>
                      {log.action}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-xs">
                    <span className="text-foreground">{log.resource_type}</span>
                    {log.resource_id && (
                      <span className="ml-1 text-muted-foreground">({log.resource_id.slice(0, 8)}\u2026)</span>
                    )}
                  </td>
                  <td className="py-2.5 text-xs text-muted-foreground max-w-[300px] truncate">
                    {Object.keys(log.details).length > 0 ? JSON.stringify(log.details) : '\u2014'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {logs.length > 0 && (
        <div className="flex items-center justify-between pt-4 mt-4">
          <span className="text-xs text-muted-foreground">
            {t('audit.showing')} {offset + 1}\u2013{offset + logs.length}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
            >
              {t('audit.prev')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setOffset(offset + limit)}
              disabled={logs.length < limit}
            >
              {t('audit.next')}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
