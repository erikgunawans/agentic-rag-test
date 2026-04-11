import { useState } from 'react'
import { FilePlus, X, Clock, CheckCircle, Pencil } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { EmptyState } from '@/components/shared/EmptyState'

type DocType = 'generic' | 'nda' | 'sales' | 'service'
type DurationUnit = 'months' | 'years' | 'days'

interface RecentDoc {
  id: string
  title: string
  type: string
  time: string
  status: 'done' | 'draft' | 'pending'
  color: string
}

const MOCK_RECENT: RecentDoc[] = [
  { id: '1', title: 'NDA_Kerahasiaan_PT_Marina.pdf', type: 'NDA', time: 'Just now', status: 'done', color: 'bg-red-500/80' },
  { id: '2', title: 'Kontrak_Distribusi_Q1.docx', type: 'Sales', time: '2h ago', status: 'done', color: 'bg-blue-500/80' },
  { id: '3', title: 'Service_Agreement_Draft.docx', type: 'Service', time: 'Yesterday', status: 'draft', color: 'bg-blue-500/80' },
  { id: '4', title: 'Generic_Compliance_Report.pdf', type: 'Generic', time: '2d ago', status: 'done', color: 'bg-red-500/80' },
]

const STATUS_ICON = {
  done: CheckCircle,
  draft: Pencil,
  pending: Clock,
}

export function DocumentCreationPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [docType, setDocType] = useState<DocType>('generic')
  const [durationUnit, setDurationUnit] = useState<DurationUnit>('months')

  return (
    <div className="flex h-full">
      {/* Left panel — scrollable form + history */}
      <div className="flex w-[300px] shrink-0 flex-col border-r border-border/50">
        <ScrollArea className="flex-1">
          <div className="p-4 space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-sm font-bold">{t('create.title')}</h1>
                <p className="text-[10px] text-muted-foreground">Fill in details to generate</p>
              </div>
              <button
                onClick={() => navigate('/')}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Document Type */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium">
                {t('create.docType')} <span className="text-red-400">*</span>
              </label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value as DocType)}
                className="w-full rounded-lg border border-border bg-secondary text-foreground px-3 py-2 text-xs"
              >
                <option value="generic">{t('create.docType.generic')}</option>
                <option value="nda">{t('create.docType.nda')}</option>
                <option value="sales">{t('create.docType.sales')}</option>
                <option value="service">{t('create.docType.service')}</option>
              </select>
            </div>

            {/* Specify document type */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium">
                Please specify document type <span className="text-red-400">*</span>
              </label>
              <Input className="text-xs" placeholder="e.g., Independent Contractor Agreement" />
            </div>

            {/* First Party */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium">
                {t('create.party1')} <span className="text-red-400">*</span>
              </label>
              <Input className="text-xs" placeholder="e.g., Buyer: John Doe" />
            </div>

            {/* Second Party */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium">{t('create.party2')}</label>
              <Input className="text-xs" placeholder="e.g., Seller: Jane Smith Inc." />
            </div>

            {/* Effective Date */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium">{t('create.effectiveDate')}</label>
              <Input type="date" className="text-xs bg-secondary text-foreground" />
            </div>

            {/* Duration Count + Unit */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-xs font-medium">Duration Count</label>
                <Input type="number" className="text-xs" placeholder="e.g., 1" />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium">Duration Unit</label>
                <select
                  value={durationUnit}
                  onChange={(e) => setDurationUnit(e.target.value as DurationUnit)}
                  className="w-full rounded-lg border border-border bg-secondary text-foreground px-3 py-2 text-xs"
                >
                  <option value="months">Months</option>
                  <option value="years">Years</option>
                  <option value="days">Days</option>
                </select>
              </div>
            </div>

            {/* Purpose */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium">
                {t('create.purpose')} <span className="text-red-400">*</span>
              </label>
              <textarea
                className="w-full rounded-lg border border-border bg-secondary text-foreground px-3 py-2 text-xs min-h-[70px] resize-none"
                placeholder="e.g., To define terms for software development services"
              />
            </div>
          </div>

          {/* Recent Documents section */}
          <div className="border-t border-border/50 p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-1.5">
                <Clock className="h-3 w-3 text-muted-foreground" />
                <span className="text-[10px] font-semibold text-muted-foreground">Recent Documents</span>
              </div>
              <span className="text-[10px] text-primary cursor-pointer hover:underline">View all →</span>
            </div>
            <div className="space-y-2">
              {MOCK_RECENT.map((doc) => {
                const StatusIcon = STATUS_ICON[doc.status]
                return (
                  <div key={doc.id} className="flex items-center gap-2 rounded-md p-1.5 hover:bg-muted/50 transition-colors cursor-pointer">
                    <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded text-[8px] font-bold text-white ${doc.color}`}>
                      {doc.title.endsWith('.pdf') ? 'PDF' : 'DOC'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] font-medium truncate">{doc.title}</p>
                      <p className="text-[9px] text-muted-foreground">
                        <span className="text-primary/70">{doc.type}</span> · {doc.time}
                      </p>
                    </div>
                    <StatusIcon className={`h-3.5 w-3.5 shrink-0 ${doc.status === 'done' ? 'text-green-400' : doc.status === 'draft' ? 'text-muted-foreground' : 'text-yellow-400'}`} />
                  </div>
                )
              })}
            </div>
          </div>
        </ScrollArea>

        {/* Generate button fixed at bottom */}
        <div className="p-4 border-t border-border/50">
          <Button className="w-full text-xs" disabled>
            <FilePlus className="mr-2 h-3.5 w-3.5" />
            {t('create.generate')}
          </Button>
        </div>
      </div>

      {/* Right panel — preview / empty state */}
      <div className="flex-1 flex flex-col items-center justify-center">
        <EmptyState
          icon={FilePlus}
          title="Fill in the form on the left to generate"
          subtitle="your document and preview it here"
        />
        <div className="flex gap-2 mt-4">
          {[
            { label: 'PDF format', color: 'bg-red-400' },
            { label: 'DOCX format', color: 'bg-blue-400' },
            { label: 'Bilingual', color: 'bg-purple-400' },
          ].map(({ label, color }) => (
            <span key={label} className="flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-[10px] text-muted-foreground">
              <span className={`h-1.5 w-1.5 rounded-full ${color}`} />
              {label}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
