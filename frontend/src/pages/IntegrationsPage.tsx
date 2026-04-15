import { useState, useEffect, useCallback } from 'react'
import { Plug, CheckCircle, XCircle, Loader2, ExternalLink } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { apiFetch } from '@/lib/api'

interface DokmeeStatus {
  configured: boolean
}

interface GoogleStatus {
  configured: boolean
  connected: boolean
}

export function IntegrationsPage() {
  const { t } = useI18n()
  const [dokmeeStatus, setDokmeeStatus] = useState<DokmeeStatus | null>(null)
  const [googleStatus, setGoogleStatus] = useState<GoogleStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState<string | null>(null)

  const loadStatuses = useCallback(async () => {
    setLoading(true)
    try {
      const [dokmeeRes, googleRes] = await Promise.allSettled([
        apiFetch('/integrations/dokmee/status'),
        apiFetch('/google/status'),
      ])
      if (dokmeeRes.status === 'fulfilled') {
        const data = await dokmeeRes.value.json()
        setDokmeeStatus(data)
      }
      if (googleRes.status === 'fulfilled') {
        const data = await googleRes.value.json()
        setGoogleStatus(data)
      }
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadStatuses()
  }, [loadStatuses])

  function showPendingMessage() {
    setMessage('This feature is pending API integration.')
    setTimeout(() => setMessage(null), 3000)
  }

  async function handleGoogleDisconnect() {
    try {
      await apiFetch('/google/disconnect', { method: 'DELETE' })
      setGoogleStatus(prev => prev ? { ...prev, connected: false } : prev)
    } catch {
      setMessage('Failed to disconnect Google Drive')
      setTimeout(() => setMessage(null), 3000)
    }
  }

  async function handleGoogleConnect() {
    try {
      const res = await apiFetch('/google/auth-url')
      const data = await res.json()
      if (data.auth_url) {
        window.open(data.auth_url, '_blank')
      }
    } catch {
      setMessage('Failed to start Google Drive connection')
      setTimeout(() => setMessage(null), 3000)
    }
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-[800px] mx-auto space-y-6">
        {/* Header */}
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Plug className="h-5 w-5 text-primary" />
            <h1 className="text-lg font-semibold">{t('nav.integrations') || 'Integrations'}</h1>
          </div>
          <p className="text-sm text-muted-foreground ml-8">
            Connect external services to your legal workspace.
          </p>
        </div>

        {/* Notification message */}
        {message && (
          <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 px-4 py-3 text-sm text-amber-600 dark:text-amber-400">
            {message}
          </div>
        )}

        {/* Dokmee Card */}
        <section className="rounded-lg border border-border/50 bg-card p-5 space-y-4" aria-label="Dokmee DMS Integration">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold">Dokmee DMS</h2>
              <p className="text-xs text-muted-foreground mt-0.5">Document management system integration</p>
            </div>
            {dokmeeStatus?.configured ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-green-500/15 px-2.5 py-0.5 text-xs font-medium text-green-600 dark:text-green-400">
                <CheckCircle className="h-3 w-3" />
                Configured
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                <XCircle className="h-3 w-3" />
                Not Configured
              </span>
            )}
          </div>

          {dokmeeStatus?.configured ? (
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" className="gap-1.5 text-xs" onClick={showPendingMessage}>
                Browse Documents
              </Button>
              <Button size="sm" variant="outline" className="gap-1.5 text-xs" onClick={showPendingMessage}>
                Import
              </Button>
              <Button size="sm" variant="outline" className="gap-1.5 text-xs" onClick={showPendingMessage}>
                Export
              </Button>
            </div>
          ) : (
            <a href="/admin/settings" className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
              <ExternalLink className="h-3 w-3" />
              Configure in Admin Settings
            </a>
          )}
        </section>

        {/* Google Drive Card */}
        <section className="rounded-lg border border-border/50 bg-card p-5 space-y-4" aria-label="Google Drive Integration">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold">Google Drive</h2>
              <p className="text-xs text-muted-foreground mt-0.5">Export documents to Google Drive</p>
            </div>
            <div className="flex items-center gap-2">
              {googleStatus?.configured ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-green-500/15 px-2.5 py-0.5 text-xs font-medium text-green-600 dark:text-green-400">
                  <CheckCircle className="h-3 w-3" />
                  Configured
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                  <XCircle className="h-3 w-3" />
                  Not Configured
                </span>
              )}
              {googleStatus?.configured && (
                googleStatus.connected ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-cyan-500/15 px-2.5 py-0.5 text-xs font-medium text-cyan-600 dark:text-cyan-400">
                    Connected
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                    Disconnected
                  </span>
                )
              )}
            </div>
          </div>

          {!googleStatus?.configured ? (
            <a href="/admin/settings" className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
              <ExternalLink className="h-3 w-3" />
              Configure in Admin Settings
            </a>
          ) : googleStatus.connected ? (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                Documents can be exported to your connected Google Drive account.
              </p>
              <Button size="sm" variant="outline" className="gap-1.5 text-xs border-red-500/30 text-red-600 dark:text-red-400 hover:bg-red-500/10 hover:text-red-300" onClick={handleGoogleDisconnect}>
                Disconnect
              </Button>
            </div>
          ) : (
            <Button size="sm" className="gap-1.5 text-xs" onClick={handleGoogleConnect}>
              Connect Google Drive
            </Button>
          )}
        </section>
      </div>
    </div>
  )
}
