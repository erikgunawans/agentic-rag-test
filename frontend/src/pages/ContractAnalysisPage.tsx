import { useState } from 'react'
import { Scale } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { FeaturePageLayout } from '@/components/shared/FeaturePageLayout'
import { SectionLabel } from '@/components/shared/SectionLabel'
import { DropZone } from '@/components/shared/DropZone'
import type { HistoryItem } from '@/components/shared/HistorySection'

type AnalysisType = 'risk' | 'obligations' | 'clauses' | 'missing'
type Law = 'indonesia' | 'singapore' | 'international' | 'custom'
type Depth = 'quick' | 'standard' | 'deep'

const MOCK_HISTORY: HistoryItem[] = [
  { id: '1', title: 'Employment-Contract.pdf', subtitle: 'Deep — High Risk', time: '2h ago' },
  { id: '2', title: 'NDA-Final.docx', subtitle: 'Standard — Low Risk', time: '1d ago' },
  { id: '3', title: 'Lease-Agreement.pdf', subtitle: 'Quick — Medium Risk', time: '3d ago' },
]

export function ContractAnalysisPage() {
  const { t } = useI18n()
  const [types, setTypes] = useState<Set<AnalysisType>>(new Set(['risk']))
  const [law, setLaw] = useState<Law>('indonesia')
  const [depth, setDepth] = useState<Depth>('standard')

  function toggleType(type: AnalysisType) {
    setTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  return (
    <FeaturePageLayout historyTitle={t('analysis.history')} historyItems={MOCK_HISTORY}>
      <div className="flex items-center gap-2 mb-2">
        <Scale className="h-5 w-5 text-[var(--feature-analysis)]" />
        <h1 className="text-lg font-semibold">{t('analysis.title')}</h1>
      </div>

      <SectionLabel label={t('analysis.document')} />
      <DropZone />

      <Separator />

      <SectionLabel label={t('analysis.type')} />
      <div className="flex flex-wrap gap-2">
        {(['risk', 'obligations', 'clauses', 'missing'] as const).map((type) => (
          <button
            key={type}
            onClick={() => toggleType(type)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              types.has(type)
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-muted-foreground hover:text-foreground'
            }`}
          >
            {t(`analysis.type.${type}`)}
          </button>
        ))}
      </div>

      <SectionLabel label={t('analysis.law')} />
      <select
        value={law}
        onChange={(e) => setLaw(e.target.value as Law)}
        className="w-full rounded-md border bg-secondary text-foreground px-3 py-2 text-sm"
      >
        <option value="indonesia">{t('analysis.law.indonesia')}</option>
        <option value="singapore">{t('analysis.law.singapore')}</option>
        <option value="international">{t('analysis.law.international')}</option>
        <option value="custom">{t('analysis.law.custom')}</option>
      </select>

      <SectionLabel label={t('analysis.depth')} />
      <div className="flex gap-2">
        {(['quick', 'standard', 'deep'] as const).map((d) => (
          <button
            key={d}
            onClick={() => setDepth(d)}
            className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              depth === d
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-muted-foreground hover:text-foreground'
            }`}
          >
            {t(`analysis.depth.${d}`)}
          </button>
        ))}
      </div>

      <SectionLabel label={t('analysis.context')} />
      <textarea
        className="w-full rounded-md border bg-secondary text-foreground px-3 py-2 text-sm min-h-[80px] resize-none"
        placeholder={t('analysis.context')}
      />

      <Button className="w-full" disabled>
        <Scale className="mr-2 h-4 w-4" />
        {t('analysis.run')}
      </Button>
    </FeaturePageLayout>
  )
}
