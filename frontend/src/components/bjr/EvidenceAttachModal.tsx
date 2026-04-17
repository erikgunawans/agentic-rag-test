import { useState } from 'react'
import { X, FileText, Sparkles, StickyNote, Link2, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n/I18nContext'
import { apiFetch } from '@/lib/api'

type EvidenceType = 'tool_result' | 'manual_note' | 'external_link'

interface EvidenceAttachModalProps {
  decisionId: string
  checklistItemId: string
  onClose: () => void
  onAttached: () => void
}

export function EvidenceAttachModal({ decisionId, checklistItemId, onClose, onAttached }: EvidenceAttachModalProps) {
  const { t } = useI18n()
  const [tab, setTab] = useState<EvidenceType>('manual_note')
  const [title, setTitle] = useState('')
  const [notes, setNotes] = useState('')
  const [externalUrl, setExternalUrl] = useState('')
  const [referenceId, setReferenceId] = useState('')
  const [loading, setLoading] = useState(false)
  const [toolResults, setToolResults] = useState<Array<{ id: string; title: string; tool_type: string; created_at: string }>>([])
  const [resultsLoaded, setResultsLoaded] = useState(false)

  const loadToolResults = async () => {
    if (resultsLoaded) return
    try {
      const res = await apiFetch('/document-tools/history?limit=20')
      const data = await res.json()
      setToolResults(data.data || [])
      setResultsLoaded(true)
    } catch {
      // silent
    }
  }

  const handleSubmit = async () => {
    if (!title.trim()) return
    setLoading(true)
    try {
      const body: Record<string, unknown> = {
        checklist_item_id: checklistItemId,
        evidence_type: tab,
        title: title.trim(),
        notes: notes.trim() || null,
      }

      if (tab === 'tool_result' && referenceId) {
        body.reference_id = referenceId
        body.reference_table = 'document_tool_results'
      }
      if (tab === 'external_link') {
        body.external_url = externalUrl.trim()
      }

      await apiFetch(`/bjr/decisions/${decisionId}/evidence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      onAttached()
    } catch {
      // error
    } finally {
      setLoading(false)
    }
  }

  const TABS: { key: EvidenceType; icon: typeof FileText; labelKey: string }[] = [
    { key: 'manual_note', icon: StickyNote, labelKey: 'bjr.evidenceType.note' },
    { key: 'tool_result', icon: Sparkles, labelKey: 'bjr.evidenceType.toolResult' },
    { key: 'external_link', icon: Link2, labelKey: 'bjr.evidenceType.link' },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="w-full max-w-lg rounded-xl border border-border bg-background p-6 shadow-lg" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold">{t('bjr.attachEvidence')}</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 rounded-lg bg-secondary p-1 mb-4">
          {TABS.map(({ key, icon: Icon, labelKey }) => (
            <button
              key={key}
              onClick={() => {
                setTab(key)
                if (key === 'tool_result') loadToolResults()
              }}
              className={`flex-1 flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                tab === key ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {t(labelKey)}
            </button>
          ))}
        </div>

        {/* Title */}
        <input
          type="text"
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder={t('bjr.evidenceTitle')}
          className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground mb-3"
        />

        {/* Tab content */}
        {tab === 'manual_note' && (
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder={t('bjr.evidenceNotes')}
            rows={4}
            className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground mb-3 resize-none"
          />
        )}

        {tab === 'tool_result' && (
          <div className="max-h-48 overflow-y-auto space-y-1 mb-3">
            {toolResults.length === 0 ? (
              <p className="text-xs text-muted-foreground italic p-2">{t('bjr.noToolResults')}</p>
            ) : (
              toolResults.map(r => (
                <button
                  key={r.id}
                  onClick={() => {
                    setReferenceId(r.id)
                    if (!title) setTitle(r.title)
                  }}
                  className={`w-full flex items-center gap-2 rounded-md px-3 py-2 text-xs text-left transition-colors ${
                    referenceId === r.id ? 'bg-primary/10 text-primary ring-1 ring-primary/30' : 'hover:bg-secondary'
                  }`}
                >
                  <Sparkles className="h-3.5 w-3.5 shrink-0" />
                  <span className="flex-1 truncate">{r.title}</span>
                  <span className="text-muted-foreground">{r.tool_type}</span>
                </button>
              ))
            )}
          </div>
        )}

        {tab === 'external_link' && (
          <input
            type="url"
            value={externalUrl}
            onChange={e => setExternalUrl(e.target.value)}
            placeholder="https://..."
            className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground mb-3"
          />
        )}

        {/* Notes for non-note tabs */}
        {tab !== 'manual_note' && (
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder={t('bjr.evidenceNotes')}
            rows={2}
            className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground mb-3 resize-none"
          />
        )}

        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose}>{t('bjr.cancel')}</Button>
          <Button size="sm" onClick={handleSubmit} disabled={loading || !title.trim()}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : t('bjr.attach')}
          </Button>
        </div>
      </div>
    </div>
  )
}
