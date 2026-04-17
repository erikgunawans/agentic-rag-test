import { useState } from 'react'
import { Check, AlertTriangle, Circle, Loader2, FileText, Link2, StickyNote, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n/I18nContext'
import { apiFetch } from '@/lib/api'

interface LLMAssessment {
  satisfies_requirement: boolean
  assessment: string
  gaps: string[]
}

interface Evidence {
  id: string
  title: string
  evidence_type: string
  review_status: string
  confidence_score: number | null
  llm_assessment: LLMAssessment | null
  created_at: string
}

interface ChecklistItemData {
  id: string
  phase: string
  item_order: number
  title: string
  description: string | null
  is_required: boolean
  regulatory_item_ids: string[]
}

interface ChecklistItemProps {
  item: ChecklistItemData
  evidence: Evidence[]
  decisionId: string
  disabled?: boolean
  onAttachEvidence: (checklistItemId: string) => void
  onRefresh: () => void
}

const STATUS_ICON: Record<string, { icon: typeof Check; color: string }> = {
  auto_approved: { icon: Check, color: 'text-green-500' },
  approved: { icon: Check, color: 'text-green-500' },
  pending_review: { icon: AlertTriangle, color: 'text-amber-500' },
  rejected: { icon: AlertTriangle, color: 'text-red-500' },
  not_assessed: { icon: Circle, color: 'text-muted-foreground' },
}

const TYPE_ICON: Record<string, typeof FileText> = {
  document: FileText,
  tool_result: Sparkles,
  manual_note: StickyNote,
  external_link: Link2,
  approval: Check,
}

export function ChecklistItem({ item, evidence, disabled, onAttachEvidence, onRefresh }: ChecklistItemProps) {
  const { t } = useI18n()
  const [assessingId, setAssessingId] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)

  const hasApproved = evidence.some(e => e.review_status === 'auto_approved' || e.review_status === 'approved')

  const handleAssess = async (evidenceId: string) => {
    setAssessingId(evidenceId)
    try {
      await apiFetch(`/bjr/evidence/${evidenceId}/assess`, { method: 'POST' })
      onRefresh()
    } catch {
      // error handled silently
    } finally {
      setAssessingId(null)
    }
  }

  return (
    <div className={`rounded-lg border p-4 transition-colors ${hasApproved ? 'border-green-500/30 bg-green-500/5' : 'border-border'}`}>
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 ${hasApproved ? 'text-green-500' : 'text-muted-foreground'}`}>
          {hasApproved ? <Check className="h-5 w-5" /> : <Circle className="h-5 w-5" />}
        </div>
        <div className="flex-1 min-w-0">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-left w-full"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">{item.title}</span>
              {item.is_required && (
                <span className="text-[10px] font-semibold uppercase tracking-wider text-red-500">
                  {t('bjr.required')}
                </span>
              )}
            </div>
            {item.description && (
              <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{item.description}</p>
            )}
          </button>

          {expanded && (
            <div className="mt-3 space-y-2">
              {evidence.length > 0 ? (
                evidence.map(ev => {
                  const StatusDef = STATUS_ICON[ev.review_status] || STATUS_ICON.not_assessed
                  const TypeIcon = TYPE_ICON[ev.evidence_type] || FileText

                  return (
                    <div key={ev.id} className="space-y-1">
                      <div className="flex items-center gap-2 rounded-md bg-secondary/50 p-2 text-xs">
                        <TypeIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                        <span className="flex-1 truncate">{ev.title}</span>
                        <StatusDef.icon className={`h-3.5 w-3.5 shrink-0 ${StatusDef.color}`} />
                        {ev.confidence_score !== null && (
                          <span className="text-muted-foreground">{Math.round(ev.confidence_score * 100)}%</span>
                        )}
                        {ev.review_status === 'not_assessed' && !disabled && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 px-2 text-[10px]"
                            disabled={assessingId === ev.id}
                            onClick={() => handleAssess(ev.id)}
                          >
                            {assessingId === ev.id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              t('bjr.assess')
                            )}
                          </Button>
                        )}
                      </div>
                      {ev.llm_assessment && (
                        <div className="ml-5 rounded-md bg-secondary/30 p-2 text-xs space-y-1">
                          <p>{ev.llm_assessment.assessment}</p>
                          {ev.llm_assessment.gaps.length > 0 && (
                            <div>
                              <span className="font-medium text-amber-500">{t('bjr.gaps')}:</span>
                              <ul className="ml-3 list-disc">
                                {ev.llm_assessment.gaps.map((g, i) => <li key={i}>{g}</li>)}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })
              ) : (
                <p className="text-xs text-muted-foreground italic">{t('bjr.noEvidence')}</p>
              )}

              {!disabled && (
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-2 h-7 text-xs"
                  onClick={() => onAttachEvidence(item.id)}
                >
                  {t('bjr.attachEvidence')}
                </Button>
              )}
            </div>
          )}
        </div>
        <span className="text-[10px] text-muted-foreground whitespace-nowrap">
          {evidence.length} {t('bjr.evidenceCount')}
        </span>
      </div>
    </div>
  )
}
