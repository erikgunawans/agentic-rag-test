import { useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { FeaturePageLayout } from '@/components/shared/FeaturePageLayout'
import { SectionLabel } from '@/components/shared/SectionLabel'
import { DropZone } from '@/components/shared/DropZone'
import type { HistoryItem } from '@/components/shared/HistorySection'

type Framework = 'ojk' | 'international' | 'gdpr' | 'custom'
type Scope = 'legal' | 'risks' | 'missing' | 'regulatory'

const MOCK_HISTORY: HistoryItem[] = [
  { id: '1', title: 'Service-Agreement.pdf', subtitle: 'OJK — Pass', time: '3h ago' },
  { id: '2', title: 'NDA-Draft.docx', subtitle: 'GDPR — Review', time: '1d ago' },
  { id: '3', title: 'Employment-Contract.pdf', subtitle: 'International — Fail', time: '4d ago' },
]

export function ComplianceCheckPage() {
  const { t } = useI18n()
  const [framework, setFramework] = useState<Framework>('ojk')
  const [scopes, setScopes] = useState<Set<Scope>>(new Set(['legal']))

  function toggleScope(scope: Scope) {
    setScopes((prev) => {
      const next = new Set(prev)
      if (next.has(scope)) next.delete(scope)
      else next.add(scope)
      return next
    })
  }

  return (
    <FeaturePageLayout historyTitle={t('compliance.history')} historyItems={MOCK_HISTORY}>
      <div className="flex items-center gap-2 mb-2">
        <ShieldCheck className="h-5 w-5 text-[var(--feature-compliance)]" />
        <h1 className="text-lg font-semibold">{t('compliance.title')}</h1>
      </div>

      <SectionLabel label={t('compliance.document')} />
      <DropZone />

      <Separator />

      <SectionLabel label={t('compliance.framework')} />
      <select
        value={framework}
        onChange={(e) => setFramework(e.target.value as Framework)}
        className="w-full rounded-md border bg-secondary text-foreground px-3 py-2 text-sm"
      >
        <option value="ojk">{t('compliance.framework.ojk')}</option>
        <option value="international">{t('compliance.framework.international')}</option>
        <option value="gdpr">{t('compliance.framework.gdpr')}</option>
        <option value="custom">{t('compliance.framework.custom')}</option>
      </select>

      <SectionLabel label={t('compliance.scope')} />
      <div className="flex flex-wrap gap-2">
        {(['legal', 'risks', 'missing', 'regulatory'] as const).map((scope) => (
          <button
            key={scope}
            onClick={() => toggleScope(scope)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              scopes.has(scope)
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-muted-foreground hover:text-foreground'
            }`}
          >
            {t(`compliance.scope.${scope}`)}
          </button>
        ))}
      </div>

      <SectionLabel label={t('compliance.context')} />
      <textarea
        className="w-full rounded-md border bg-secondary text-foreground px-3 py-2 text-sm min-h-[80px] resize-none"
        placeholder={t('compliance.context')}
      />

      <Button className="w-full" disabled>
        <ShieldCheck className="mr-2 h-4 w-4" />
        {t('compliance.run')}
      </Button>
    </FeaturePageLayout>
  )
}
