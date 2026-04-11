import { useState } from 'react'
import { FilePlus } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { FeaturePageLayout } from '@/components/shared/FeaturePageLayout'
import { SectionLabel } from '@/components/shared/SectionLabel'
import { DropZone } from '@/components/shared/DropZone'
import type { HistoryItem } from '@/components/shared/HistorySection'

type DocType = 'generic' | 'nda' | 'sales' | 'service'

const MOCK_HISTORY: HistoryItem[] = [
  { id: '1', title: 'NDA-2026-001.docx', subtitle: 'NDA', time: '2h ago' },
  { id: '2', title: 'Service-Agreement.pdf', subtitle: 'Service', time: '1d ago' },
  { id: '3', title: 'Sales-Contract.docx', subtitle: 'Sales', time: '3d ago' },
]

export function DocumentCreationPage() {
  const { t } = useI18n()
  const [docType, setDocType] = useState<DocType>('generic')
  const [language, setLanguage] = useState<'bilingual' | 'id'>('bilingual')

  return (
    <FeaturePageLayout historyTitle={t('create.history')} historyItems={MOCK_HISTORY}>
      <div className="flex items-center gap-2 mb-2">
        <FilePlus className="h-5 w-5 text-[var(--feature-creation)]" />
        <h1 className="text-lg font-semibold">{t('create.title')}</h1>
      </div>

      <SectionLabel label={t('create.docType')} />
      <select
        value={docType}
        onChange={(e) => setDocType(e.target.value as DocType)}
        className="w-full rounded-md border bg-secondary text-foreground px-3 py-2 text-sm"
      >
        <option value="generic">{t('create.docType.generic')}</option>
        <option value="nda">{t('create.docType.nda')}</option>
        <option value="sales">{t('create.docType.sales')}</option>
        <option value="service">{t('create.docType.service')}</option>
      </select>

      <Separator />

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <SectionLabel label={t('create.party1')} />
          <Input placeholder={t('create.party1')} />
        </div>
        <div className="space-y-1">
          <SectionLabel label={t('create.party2')} />
          <Input placeholder={t('create.party2')} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <SectionLabel label={t('create.effectiveDate')} />
          <Input type="date" className="bg-secondary text-foreground" />
        </div>
        <div className="space-y-1">
          <SectionLabel label={t('create.duration')} />
          <Input placeholder="12 months" />
        </div>
      </div>

      <div className="space-y-1">
        <SectionLabel label={t('create.purpose')} />
        <Input placeholder={t('create.purpose')} />
      </div>

      <div className="space-y-1">
        <SectionLabel label={t('create.governingLaw')} />
        <Input placeholder="Indonesian Law" />
      </div>

      <div className="space-y-1">
        <SectionLabel label={t('create.notes')} />
        <textarea
          className="w-full rounded-md border bg-secondary text-foreground px-3 py-2 text-sm min-h-[80px] resize-none"
          placeholder={t('create.notes')}
        />
      </div>

      <Separator />

      <SectionLabel label={t('create.language')} />
      <div className="flex gap-2">
        {(['bilingual', 'id'] as const).map((opt) => (
          <button
            key={opt}
            onClick={() => setLanguage(opt)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              language === opt
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-muted-foreground hover:text-foreground'
            }`}
          >
            {t(`create.language.${opt}`)}
          </button>
        ))}
      </div>

      <Separator />

      <SectionLabel label={t('create.reference')} />
      <DropZone />

      <SectionLabel label={t('create.template')} />
      <DropZone />

      <Button className="w-full" disabled>
        <FilePlus className="mr-2 h-4 w-4" />
        {t('create.generate')}
      </Button>
    </FeaturePageLayout>
  )
}
