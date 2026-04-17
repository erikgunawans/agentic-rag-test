import { useCallback, useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2, Send, AlertTriangle } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { PhaseProgress } from '@/components/bjr/PhaseProgress'
import { ChecklistItem } from '@/components/bjr/ChecklistItem'
import { EvidenceAttachModal } from '@/components/bjr/EvidenceAttachModal'
import { RiskCard } from '@/components/bjr/RiskCard'
import { useI18n } from '@/i18n/I18nContext'

interface Decision {
  id: string
  title: string
  description: string | null
  decision_type: string
  current_phase: string
  status: string
  risk_level: string | null
  bjr_score: number
  user_email: string
  estimated_value: number | null
  gcg_aspect_ids: string[]
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

interface Evidence {
  id: string
  checklist_item_id: string
  title: string
  evidence_type: string
  review_status: string
  confidence_score: number | null
  llm_assessment: {
    satisfies_requirement: boolean
    assessment: string
    gaps: string[]
  } | null
  created_at: string
}

interface Risk {
  id: string
  risk_title: string
  description: string | null
  risk_level: string
  mitigation: string | null
  status: string
  owner_role: string | null
  is_global: boolean
}

const TYPE_LABELS: Record<string, string> = {
  investment: 'Investasi',
  procurement: 'Pengadaan',
  partnership: 'Kemitraan',
  divestment: 'Divestasi',
  capex: 'Capex',
  policy: 'Kebijakan',
  other: 'Lainnya',
}

export function BJRDecisionPage() {
  const { t } = useI18n()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [decision, setDecision] = useState<Decision | null>(null)
  const [checklist, setChecklist] = useState<ChecklistItemData[]>([])
  const [evidence, setEvidence] = useState<Evidence[]>([])
  const [risks, setRisks] = useState<Risk[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [selectedPhase, setSelectedPhase] = useState('')
  const [attachModal, setAttachModal] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    if (!id) return
    setLoading(true)
    try {
      const res = await apiFetch(`/bjr/decisions/${id}`)
      const data = await res.json()
      setDecision(data.decision)
      setChecklist(data.checklist)
      setEvidence(data.evidence)
      setRisks(data.risks)
      if (!selectedPhase) setSelectedPhase(data.decision.current_phase === 'completed' ? 'post_decision' : data.decision.current_phase)
    } catch {
      // error
    } finally {
      setLoading(false)
    }
  }, [id, selectedPhase])

  useEffect(() => { loadData() }, [loadData])

  const handleSubmitPhase = async () => {
    if (!id) return
    setSubmitting(true)
    try {
      await apiFetch(`/bjr/decisions/${id}/submit-phase`, { method: 'POST' })
      loadData()
    } catch {
      // error
    } finally {
      setSubmitting(false)
    }
  }

  const handleUpdateRiskStatus = async (riskId: string, status: string) => {
    try {
      await apiFetch(`/bjr/risks/${riskId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      loadData()
    } catch {
      // error
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!decision) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
        <AlertTriangle className="h-8 w-8 mb-2" />
        <p>{t('bjr.notFound')}</p>
      </div>
    )
  }

  const phaseChecklist = checklist.filter(c => c.phase === selectedPhase)
  const isCurrentPhase = selectedPhase === decision.current_phase
  const isCompleted = decision.current_phase === 'completed'
  const canSubmit = isCurrentPhase && !isCompleted && decision.status !== 'under_review'

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div>
          <button
            onClick={() => navigate('/bjr')}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-3"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            {t('bjr.backToList')}
          </button>

          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-extrabold tracking-tight">{decision.title}</h1>
              <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                <span className="bg-secondary px-1.5 py-0.5 rounded font-medium">
                  {TYPE_LABELS[decision.decision_type] || decision.decision_type}
                </span>
                {decision.risk_level && (
                  <span className={`font-semibold uppercase ${
                    decision.risk_level === 'high' || decision.risk_level === 'critical' ? 'text-red-500' :
                    decision.risk_level === 'medium' ? 'text-amber-500' : 'text-green-500'
                  }`}>
                    {t('bjr.risk')}: {decision.risk_level}
                  </span>
                )}
                {decision.estimated_value && (
                  <span>IDR {Number(decision.estimated_value).toLocaleString('id-ID')}</span>
                )}
                <span>{decision.user_email}</span>
              </div>
              {decision.description && (
                <p className="mt-2 text-sm text-muted-foreground">{decision.description}</p>
              )}
            </div>

            {/* BJR Score */}
            <div className="text-center shrink-0">
              <div className="relative w-16 h-16">
                <svg className="w-16 h-16 -rotate-90" viewBox="0 0 36 36">
                  <path
                    className="text-secondary"
                    strokeWidth="3"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  <path
                    className="text-primary"
                    strokeWidth="3"
                    stroke="currentColor"
                    fill="none"
                    strokeDasharray={`${decision.bjr_score}, 100`}
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-sm font-bold">
                  {Math.round(decision.bjr_score)}%
                </span>
              </div>
              <p className="text-[10px] text-muted-foreground mt-1">BJR Score</p>
            </div>
          </div>
        </div>

        {/* Phase Stepper */}
        <PhaseProgress
          currentPhase={decision.current_phase}
          selectedPhase={selectedPhase}
          onSelectPhase={setSelectedPhase}
        />

        {/* Status Banner */}
        {decision.status === 'under_review' && isCurrentPhase && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-600 dark:text-amber-400 flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            {t('bjr.phaseUnderReview')}
          </div>
        )}

        {/* Checklist */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold">
              {t('bjr.checklist')} — {t(`bjr.phase.${selectedPhase}`)}
            </h2>
            {canSubmit && (
              <Button size="sm" onClick={handleSubmitPhase} disabled={submitting}>
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Send className="h-4 w-4 mr-2" />
                )}
                {t('bjr.submitPhase')}
              </Button>
            )}
          </div>

          <div className="space-y-2">
            {phaseChecklist.map(item => (
              <ChecklistItem
                key={item.id}
                item={item}
                evidence={evidence.filter(e => e.checklist_item_id === item.id)}
                decisionId={decision.id}
                disabled={!isCurrentPhase || isCompleted || decision.status === 'under_review'}
                onAttachEvidence={(checklistItemId) => setAttachModal(checklistItemId)}
                onRefresh={loadData}
              />
            ))}
          </div>
        </div>

        {/* Risks */}
        {risks.length > 0 && (
          <div>
            <h2 className="text-sm font-semibold mb-3">{t('bjr.riskRegister')}</h2>
            <div className="space-y-2">
              {risks.map(r => (
                <RiskCard
                  key={r.id}
                  risk={r}
                  onUpdateStatus={!isCompleted ? handleUpdateRiskStatus : undefined}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Evidence Attach Modal */}
      {attachModal && (
        <EvidenceAttachModal
          decisionId={decision.id}
          checklistItemId={attachModal}
          onClose={() => setAttachModal(null)}
          onAttached={() => {
            setAttachModal(null)
            loadData()
          }}
        />
      )}
    </div>
  )
}
