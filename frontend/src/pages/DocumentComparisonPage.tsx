import { useState } from 'react'
import { GitCompare, ArrowLeftRight } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { FeaturePageLayout } from '@/components/shared/FeaturePageLayout'
import { SectionLabel } from '@/components/shared/SectionLabel'
import { DropZone } from '@/components/shared/DropZone'
import type { HistoryItem } from '@/components/shared/HistorySection'

type ComparisonFocus = 'full' | 'clauses' | 'risks'

const MOCK_HISTORY: HistoryItem[] = [
  { id: '1', title: 'NDA v1 vs NDA v2', subtitle: 'Full Document', time: '1h ago' },
  { id: '2', title: 'Contract A vs Contract B', subtitle: 'Key Clauses', time: '2d ago' },
  { id: '3', title: 'Draft vs Final', subtitle: 'Risk Differences', time: '5d ago' },
]

export function DocumentComparisonPage() {
  const { t } = useI18n()
  const [focus, setFocus] = useState<ComparisonFocus>('full')

  return (
    <FeaturePageLayout historyTitle={t('compare.history')} historyItems={MOCK_HISTORY}>
      <div className="flex items-center gap-2 mb-2">
        <GitCompare className="h-5 w-5 text-[var(--feature-management)]" />
        <h1 className="text-lg font-semibold">{t('compare.title')}</h1>
      </div>

      <SectionLabel label={t('compare.doc1')} />
      <DropZone label={t('compare.doc1')} />

      <div className="flex justify-center">
        <button
          className="flex h-8 w-8 items-center justify-center rounded-full border border-border text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          title={t('compare.swap')}
        >
          <ArrowLeftRight className="h-4 w-4" />
        </button>
      </div>

      <SectionLabel label={t('compare.doc2')} />
      <DropZone label={t('compare.doc2')} />

      <Separator />

      <SectionLabel label={t('compare.focus')} />
      <div className="flex gap-2">
        {(['full', 'clauses', 'risks'] as const).map((opt) => (
          <button
            key={opt}
            onClick={() => setFocus(opt)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              focus === opt
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-muted-foreground hover:text-foreground'
            }`}
          >
            {t(`compare.focus.${opt}`)}
          </button>
        ))}
      </div>

      <Button className="w-full" disabled>
        <GitCompare className="mr-2 h-4 w-4" />
        {t('compare.generate')}
      </Button>
    </FeaturePageLayout>
  )
}
