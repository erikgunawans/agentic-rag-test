import { useState } from 'react'
import { FilePlus, X, Clock, CheckCircle, Pencil, XCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { DropZone } from '@/components/shared/DropZone'
import { EmptyState } from '@/components/shared/EmptyState'

type DocType = 'generic' | 'nda' | 'sales' | 'service'

// --- Form field helper ---
function FormField({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium">
        {label} {required && <span className="text-red-400">*</span>}
      </label>
      {children}
    </div>
  )
}

const inputClass = "w-full rounded-lg border border-border bg-secondary text-foreground px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
const textareaClass = `${inputClass} min-h-[80px] resize-none`

// --- Dynamic form renderers ---
function GenericForm() {
  return (
    <>
      <FormField label="Please specify document type" required>
        <input className={inputClass} placeholder="e.g., Independent Contractor Agreement" />
      </FormField>
      <FormField label="First Party" required>
        <input className={inputClass} placeholder="e.g., Buyer: John Doe" />
      </FormField>
      <FormField label="Second Party">
        <input className={inputClass} placeholder="e.g., Seller: Jane Smith Inc." />
      </FormField>
      <FormField label="Effective Date">
        <Input type="date" className="text-xs bg-secondary" />
      </FormField>
      <div className="grid grid-cols-[1fr_1fr] gap-2.5">
        <FormField label="Duration Count">
          <input type="number" className={inputClass} placeholder="e.g., 1" />
        </FormField>
        <FormField label="Duration Unit">
          <select className={inputClass}>
            <option value="">Select an option</option>
            <option value="days">Days</option>
            <option value="months">Months</option>
            <option value="years">Years</option>
          </select>
        </FormField>
      </div>
      <FormField label="Purpose of the document" required>
        <textarea className={textareaClass} placeholder="e.g., To define terms for software development services" />
      </FormField>
    </>
  )
}

function NDAForm() {
  return (
    <>
      <FormField label="Disclosing Party" required>
        <input className={inputClass} placeholder="e.g., Company A Inc." />
      </FormField>
      <FormField label="Receiving Party" required>
        <input className={inputClass} placeholder="e.g., Consultant X LLC" />
      </FormField>
      <FormField label="Purpose of Disclosure" required>
        <textarea className={textareaClass} placeholder="e.g., Evaluation of potential business partnership" />
      </FormField>
      <FormField label="Definition of Confidential Information" required>
        <textarea className={textareaClass} />
      </FormField>
      <FormField label="Obligations of Receiving Party">
        <select className={inputClass}>
          <option value="">Select an option</option>
          <option value="standard">Standard confidentiality obligations</option>
          <option value="enhanced">Enhanced confidentiality obligations</option>
        </select>
      </FormField>
      <FormField label="Term of Agreement" required>
        <input className={inputClass} placeholder="e.g., 5 years from effective date, indefinite" />
      </FormField>
      <FormField label="Return/Destruction of Confidential Information" required>
        <input className={inputClass} placeholder="Upon termination or request" />
      </FormField>
      <FormField label="Governing Law" required>
        <input className={inputClass} defaultValue="Indonesia" />
      </FormField>
      <FormField label="Additional Notes or Specific Requirements">
        <textarea className={`${inputClass} min-h-[64px] resize-none`} />
      </FormField>
    </>
  )
}

function SalesServiceForm() {
  return (
    <>
      <FormField label="First Party" required>
        <input className={inputClass} placeholder="e.g., Buyer: John Doe" />
      </FormField>
      <FormField label="Second Party" required>
        <input className={inputClass} placeholder="e.g., Seller: Jane Smith Inc." />
      </FormField>
      <FormField label="Effective Date" required>
        <Input type="date" className="text-xs bg-secondary" />
      </FormField>
      <div className="grid grid-cols-[1fr_1fr] gap-2.5">
        <FormField label="Duration Count" required>
          <input type="number" className={inputClass} placeholder="e.g., 1" />
        </FormField>
        <FormField label="Duration Unit" required>
          <select className={inputClass}>
            <option value="">Select an option</option>
            <option value="days">Days</option>
            <option value="months">Months</option>
            <option value="years">Years</option>
          </select>
        </FormField>
      </div>
      <FormField label="Purpose of the document" required>
        <textarea className={textareaClass} />
      </FormField>
      <FormField label="Scope of Work" required>
        <textarea className={textareaClass} />
      </FormField>
      <FormField label="Deliverables" required>
        <textarea className={textareaClass} />
      </FormField>
      <FormField label="Payment Terms (Optional)">
        <input className={inputClass} />
      </FormField>
      <FormField label="Governing Law" required>
        <input className={inputClass} defaultValue="Indonesia" />
      </FormField>
      <FormField label="Additional Notes or Specific Requirements">
        <textarea className={`${inputClass} min-h-[64px] resize-none`} />
      </FormField>
    </>
  )
}

// --- Recent documents data ---
interface RecentDoc {
  id: string
  title: string
  type: string
  time: string
  status: 'done' | 'draft' | 'failed'
  fileExt: 'pdf' | 'docx'
}

const MOCK_RECENT: RecentDoc[] = [
  { id: '1', title: 'NDA_Kerahasiaan_PT_Marina.pdf', type: 'NDA', time: 'Just now', status: 'done', fileExt: 'pdf' },
  { id: '2', title: 'Kontrak_Distribusi_Q1.docx', type: 'Sales', time: '2h ago', status: 'done', fileExt: 'docx' },
  { id: '3', title: 'Service_Agreement_Draft.docx', type: 'Service', time: 'Yesterday', status: 'draft', fileExt: 'docx' },
  { id: '4', title: 'Generic_Compliance_Report.pdf', type: 'Generic', time: '2d ago', status: 'done', fileExt: 'pdf' },
  { id: '5', title: 'NDA_Proyek_Ekspansi.docx', type: 'NDA', time: '3d ago', status: 'done', fileExt: 'docx' },
  { id: '6', title: 'Sales_Contract_Retail.pdf', type: 'Sales', time: '4d ago', status: 'failed', fileExt: 'pdf' },
  { id: '7', title: 'Perjanjian_Lisensi_SW.docx', type: 'Generic', time: '5d ago', status: 'done', fileExt: 'docx' },
]

const STATUS_ICON = { done: CheckCircle, draft: Pencil, failed: XCircle }
const STATUS_COLOR = { done: 'text-green-400', draft: 'text-muted-foreground', failed: 'text-red-400' }
const FILE_COLOR = { pdf: 'bg-red-500/15 text-red-400', docx: 'bg-cyan-500/15 text-cyan-400' }

// --- Main page ---
export function DocumentCreationPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [docType, setDocType] = useState<DocType>('generic')
  const [outputLang, setOutputLang] = useState<'both' | 'indonesian'>('both')

  const generateLabel = docType === 'nda' ? 'Generate NDA' : 'Generate Draft'

  return (
    <div className="flex h-full">
      {/* Column 2 — Form (top 75%) + History (bottom 25%) */}
      <div className="flex w-[340px] shrink-0 flex-col border-r border-border/50">

        {/* Header — fixed */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border/50 shrink-0">
          <div>
            <h1 className="text-sm font-semibold">{t('create.title')}</h1>
            <p className="text-[10px] text-muted-foreground">Fill in details to generate</p>
          </div>
          <button onClick={() => navigate('/')} className="text-muted-foreground hover:text-foreground transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Form area — takes 75% of remaining height, scrolls independently */}
        <div className="min-h-0 overflow-y-auto" style={{ flex: '3 1 0' }}>
          <div className="px-5 py-4 space-y-4">
              {/* Document Type — always shown */}
              <FormField label="Document Type" required>
                <select
                  value={docType}
                  onChange={(e) => setDocType(e.target.value as DocType)}
                  className={inputClass}
                >
                  <option value="generic">Generic Document</option>
                  <option value="nda">NDA</option>
                  <option value="sales">Sales Contract</option>
                  <option value="service">Service Contract</option>
                </select>
              </FormField>

              {/* Dynamic fields per type */}
              {docType === 'generic' && <GenericForm />}
              {docType === 'nda' && <NDAForm />}
              {(docType === 'sales' || docType === 'service') && <SalesServiceForm />}

              {/* Output Language */}
              <div className="space-y-2.5 pt-2">
                <label className="text-xs font-medium">Output Language</label>
                <div className="flex flex-col gap-2.5">
                  {([
                    { value: 'both', label: 'English & Indonesian' },
                    { value: 'indonesian', label: 'Indonesian Only' },
                  ] as const).map(({ value, label }) => (
                    <button key={value} onClick={() => setOutputLang(value)} className="flex items-center gap-2">
                      <div className={`h-4 w-4 rounded-full border-2 flex items-center justify-center shrink-0 ${outputLang === value ? 'border-primary' : 'border-muted-foreground'}`}>
                        {outputLang === value && <div className="h-2 w-2 rounded-full bg-primary" />}
                      </div>
                      <span className="text-xs text-foreground">{label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Reference Document */}
              <FormField label="Reference Document (Optional)">
                <DropZone />
              </FormField>

              {/* Template */}
              <FormField label="Template Document (Optional)">
                <DropZone />
              </FormField>

              {/* Generate button */}
              <Button className="w-full text-xs" disabled>
                <FilePlus className="mr-2 h-3.5 w-3.5" />
                {generateLabel}
              </Button>
            </div>
        </div>

        {/* History area — takes 25% of remaining height, scrolls independently */}
        <div className="min-h-0 flex flex-col border-t border-border/50" style={{ flex: '1 1 0' }}>
          <div className="flex items-center justify-between px-5 py-2.5 shrink-0">
            <div className="flex items-center gap-1.5">
              <Clock className="h-3 w-3 text-muted-foreground" />
              <span className="text-[10px] font-semibold text-muted-foreground">Recent Documents</span>
            </div>
            <span className="text-[10px] text-primary cursor-pointer hover:underline">View all →</span>
          </div>
          <div className="flex-1 overflow-y-auto min-h-0">
            <div className="px-3 pb-2 space-y-0.5">
              {MOCK_RECENT.map((doc) => {
                const StatusIcon = STATUS_ICON[doc.status]
                return (
                  <div key={doc.id} className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted/50 transition-colors cursor-pointer">
                    <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded text-[7px] font-bold ${FILE_COLOR[doc.fileExt]}`}>
                      {doc.fileExt.toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] font-medium truncate">{doc.title}</p>
                      <p className="text-[9px] text-muted-foreground">
                        <span className="text-primary/70">{doc.type}</span> · {doc.time}
                      </p>
                    </div>
                    <StatusIcon className={`h-3.5 w-3.5 shrink-0 ${STATUS_COLOR[doc.status]}`} />
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Column 3 — Preview / empty state */}
      <div className="flex-1 flex flex-col items-center justify-center">
        <EmptyState
          icon={FilePlus}
          title="Fill in the form on the left to generate"
          subtitle="your document and preview it here"
        />
        <div className="flex gap-2 mt-4">
          {[
            { label: 'PDF format', color: 'bg-red-400' },
            { label: 'DOCX format', color: 'bg-cyan-400' },
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
