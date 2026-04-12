import { useState } from 'react'
import { FilePlus, ChevronLeft, ChevronRight, Clock, CheckCircle, XCircle, Loader2, FileText } from 'lucide-react'
import { useToolHistory, formatTimeAgo } from '@/hooks/useToolHistory'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { DropZone } from '@/components/shared/DropZone'
import { EmptyState } from '@/components/shared/EmptyState'
import { apiFetch } from '@/lib/api'

type DocType = 'generic' | 'nda' | 'sales' | 'service'

interface GeneratedDocument {
  title: string
  content: string
  summary: string
}

// --- Form field helper ---
function FormField({ label, required, error, children }: { label: string; required?: boolean; error?: boolean; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium">
        {label} {required && <span className="text-red-400">*</span>}
      </label>
      {children}
      {error && <p className="text-[10px] text-red-400">This field is required</p>}
    </div>
  )
}

const inputBase = "w-full rounded-lg bg-secondary text-foreground px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
const inputClass = `${inputBase} border border-border`
const inputErrorClass = `${inputBase} border border-red-500/50`
const textareaClass = `${inputClass} min-h-[80px] resize-none`
const textareaErrorClass = `${inputErrorClass} min-h-[80px] resize-none`

// --- Dynamic form renderers ---
function GenericForm({ fields, onChange, fieldErr }: { fields: Record<string, string>; onChange: (key: string, val: string) => void; fieldErr: (k: string) => boolean }) {
  return (
    <>
      <FormField label="Please specify document type" required error={fieldErr('document_type')}>
        <input className={fieldErr('document_type') ? inputErrorClass : inputClass} placeholder="e.g., Independent Contractor Agreement" value={fields.document_type || ''} onChange={(e) => onChange('document_type', e.target.value)} />
      </FormField>
      <FormField label="First Party" required error={fieldErr('first_party')}>
        <input className={fieldErr('first_party') ? inputErrorClass : inputClass} placeholder="e.g., Buyer: John Doe" value={fields.first_party || ''} onChange={(e) => onChange('first_party', e.target.value)} />
      </FormField>
      <FormField label="Second Party">
        <input className={inputClass} placeholder="e.g., Seller: Jane Smith Inc." value={fields.second_party || ''} onChange={(e) => onChange('second_party', e.target.value)} />
      </FormField>
      <FormField label="Effective Date">
        <Input type="date" className="text-xs bg-secondary" value={fields.effective_date || ''} onChange={(e) => onChange('effective_date', e.target.value)} />
      </FormField>
      <div className="grid grid-cols-[1fr_1fr] gap-2.5">
        <FormField label="Duration Count">
          <input type="number" className={inputClass} placeholder="e.g., 1" value={fields.duration_count || ''} onChange={(e) => onChange('duration_count', e.target.value)} />
        </FormField>
        <FormField label="Duration Unit">
          <select className={inputClass} value={fields.duration_unit || ''} onChange={(e) => onChange('duration_unit', e.target.value)}>
            <option value="">Select an option</option>
            <option value="days">Days</option>
            <option value="months">Months</option>
            <option value="years">Years</option>
          </select>
        </FormField>
      </div>
      <FormField label="Purpose of the document" required error={fieldErr('purpose')}>
        <textarea className={fieldErr('purpose') ? textareaErrorClass : textareaClass} placeholder="e.g., To define terms for software development services" value={fields.purpose || ''} onChange={(e) => onChange('purpose', e.target.value)} />
      </FormField>
    </>
  )
}

function NDAForm({ fields, onChange, fieldErr }: { fields: Record<string, string>; onChange: (key: string, val: string) => void; fieldErr: (k: string) => boolean }) {
  return (
    <>
      <FormField label="Disclosing Party" required error={fieldErr('disclosing_party')}>
        <input className={fieldErr('disclosing_party') ? inputErrorClass : inputClass} placeholder="e.g., Company A Inc." value={fields.disclosing_party || ''} onChange={(e) => onChange('disclosing_party', e.target.value)} />
      </FormField>
      <FormField label="Receiving Party" required error={fieldErr('receiving_party')}>
        <input className={fieldErr('receiving_party') ? inputErrorClass : inputClass} placeholder="e.g., Consultant X LLC" value={fields.receiving_party || ''} onChange={(e) => onChange('receiving_party', e.target.value)} />
      </FormField>
      <FormField label="Purpose of Disclosure" required error={fieldErr('purpose')}>
        <textarea className={fieldErr('purpose') ? textareaErrorClass : textareaClass} placeholder="e.g., Evaluation of potential business partnership" value={fields.purpose || ''} onChange={(e) => onChange('purpose', e.target.value)} />
      </FormField>
      <FormField label="Definition of Confidential Information" required error={fieldErr('confidential_info')}>
        <textarea className={fieldErr('confidential_info') ? textareaErrorClass : textareaClass} value={fields.confidential_info || ''} onChange={(e) => onChange('confidential_info', e.target.value)} />
      </FormField>
      <FormField label="Obligations of Receiving Party">
        <select className={inputClass} value={fields.obligations || ''} onChange={(e) => onChange('obligations', e.target.value)}>
          <option value="">Select an option</option>
          <option value="standard">Standard confidentiality obligations</option>
          <option value="enhanced">Enhanced confidentiality obligations</option>
        </select>
      </FormField>
      <FormField label="Term of Agreement" required error={fieldErr('term')}>
        <input className={fieldErr('term') ? inputErrorClass : inputClass} placeholder="e.g., 5 years from effective date, indefinite" value={fields.term || ''} onChange={(e) => onChange('term', e.target.value)} />
      </FormField>
      <FormField label="Return/Destruction of Confidential Information" required error={fieldErr('return_destruction')}>
        <input className={fieldErr('return_destruction') ? inputErrorClass : inputClass} placeholder="Upon termination or request" value={fields.return_destruction || ''} onChange={(e) => onChange('return_destruction', e.target.value)} />
      </FormField>
      <FormField label="Governing Law" required error={fieldErr('governing_law')}>
        <input className={fieldErr('governing_law') ? inputErrorClass : inputClass} value={fields.governing_law || 'Indonesia'} onChange={(e) => onChange('governing_law', e.target.value)} />
      </FormField>
      <FormField label="Additional Notes or Specific Requirements">
        <textarea className={`${inputClass} min-h-[64px] resize-none`} value={fields.additional_notes || ''} onChange={(e) => onChange('additional_notes', e.target.value)} />
      </FormField>
    </>
  )
}

function SalesServiceForm({ fields, onChange, fieldErr }: { fields: Record<string, string>; onChange: (key: string, val: string) => void; fieldErr: (k: string) => boolean }) {
  return (
    <>
      <FormField label="First Party" required error={fieldErr('first_party')}>
        <input className={fieldErr('first_party') ? inputErrorClass : inputClass} placeholder="e.g., Buyer: John Doe" value={fields.first_party || ''} onChange={(e) => onChange('first_party', e.target.value)} />
      </FormField>
      <FormField label="Second Party" required error={fieldErr('second_party')}>
        <input className={fieldErr('second_party') ? inputErrorClass : inputClass} placeholder="e.g., Seller: Jane Smith Inc." value={fields.second_party || ''} onChange={(e) => onChange('second_party', e.target.value)} />
      </FormField>
      <FormField label="Effective Date" required error={fieldErr('effective_date')}>
        <Input type="date" className={`text-xs bg-secondary ${fieldErr('effective_date') ? 'border-red-500/50' : ''}`} value={fields.effective_date || ''} onChange={(e) => onChange('effective_date', e.target.value)} />
      </FormField>
      <div className="grid grid-cols-[1fr_1fr] gap-2.5">
        <FormField label="Duration Count" required error={fieldErr('duration_count')}>
          <input type="number" className={fieldErr('duration_count') ? inputErrorClass : inputClass} placeholder="e.g., 1" value={fields.duration_count || ''} onChange={(e) => onChange('duration_count', e.target.value)} />
        </FormField>
        <FormField label="Duration Unit" required error={fieldErr('duration_unit')}>
          <select className={fieldErr('duration_unit') ? inputErrorClass : inputClass} value={fields.duration_unit || ''} onChange={(e) => onChange('duration_unit', e.target.value)}>
            <option value="">Select an option</option>
            <option value="days">Days</option>
            <option value="months">Months</option>
            <option value="years">Years</option>
          </select>
        </FormField>
      </div>
      <FormField label="Purpose of the document" required error={fieldErr('purpose')}>
        <textarea className={fieldErr('purpose') ? textareaErrorClass : textareaClass} value={fields.purpose || ''} onChange={(e) => onChange('purpose', e.target.value)} />
      </FormField>
      <FormField label="Scope of Work" required error={fieldErr('scope_of_work')}>
        <textarea className={fieldErr('scope_of_work') ? textareaErrorClass : textareaClass} value={fields.scope_of_work || ''} onChange={(e) => onChange('scope_of_work', e.target.value)} />
      </FormField>
      <FormField label="Deliverables" required error={fieldErr('deliverables')}>
        <textarea className={fieldErr('deliverables') ? textareaErrorClass : textareaClass} value={fields.deliverables || ''} onChange={(e) => onChange('deliverables', e.target.value)} />
      </FormField>
      <FormField label="Payment Terms (Optional)">
        <input className={inputClass} value={fields.payment_terms || ''} onChange={(e) => onChange('payment_terms', e.target.value)} />
      </FormField>
      <FormField label="Governing Law" required error={fieldErr('governing_law')}>
        <input className={fieldErr('governing_law') ? inputErrorClass : inputClass} value={fields.governing_law || 'Indonesia'} onChange={(e) => onChange('governing_law', e.target.value)} />
      </FormField>
      <FormField label="Additional Notes or Specific Requirements">
        <textarea className={`${inputClass} min-h-[64px] resize-none`} value={fields.additional_notes || ''} onChange={(e) => onChange('additional_notes', e.target.value)} />
      </FormField>
    </>
  )
}

// --- Recent documents ---

// --- Main page ---
export function DocumentCreationPage() {
  const { t } = useI18n()
  const { history, reload: reloadHistory } = useToolHistory('create')
  const [panelCollapsed, setPanelCollapsed] = useState(false)
  const [docType, setDocType] = useState<DocType>('generic')
  const [outputLang, setOutputLang] = useState<'both' | 'indonesian'>('both')
  const [fields, setFields] = useState<Record<string, string>>({})
  const [referenceFile, setReferenceFile] = useState<File | null>(null)
  const [templateFile, setTemplateFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<GeneratedDocument | null>(null)
  const [showErrors, setShowErrors] = useState(false)

  function updateField(key: string, value: string) {
    setFields((prev) => ({ ...prev, [key]: value }))
  }

  function handleDocTypeChange(newType: DocType) {
    setDocType(newType)
    setFields({})
    setShowErrors(false)
  }

  async function handleGenerate() {
    setLoading(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('doc_type', docType)
      formData.append('fields', JSON.stringify(fields))
      formData.append('output_language', outputLang)
      if (referenceFile) formData.append('reference_file', referenceFile)
      if (templateFile) formData.append('template_file', templateFile)

      const response = await apiFetch('/document-tools/create', {
        method: 'POST',
        body: formData,
      })
      const data = await response.json()
      setResult(data)
      reloadHistory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate document')
    } finally {
      setLoading(false)
    }
  }

  const REQUIRED_FIELDS: Record<DocType, string[]> = {
    generic: ['document_type', 'first_party', 'purpose'],
    nda: ['disclosing_party', 'receiving_party', 'purpose', 'confidential_info', 'term', 'return_destruction', 'governing_law'],
    sales: ['first_party', 'second_party', 'effective_date', 'duration_count', 'duration_unit', 'purpose', 'scope_of_work', 'deliverables', 'governing_law'],
    service: ['first_party', 'second_party', 'effective_date', 'duration_count', 'duration_unit', 'purpose', 'scope_of_work', 'deliverables', 'governing_law'],
  }
  const canGenerate = !loading && REQUIRED_FIELDS[docType].every((key) => fields[key]?.trim())
  function fieldErr(key: string): boolean {
    return showErrors && REQUIRED_FIELDS[docType].includes(key) && !fields[key]?.trim()
  }

  const generateLabel = docType === 'nda' ? 'Generate NDA' : 'Generate Draft'

  return (
    <div className="flex h-full">
      {/* Column 2 -- Form (top 75%) + History (bottom 25%) */}
      {panelCollapsed ? (
        <div className="flex h-full w-[50px] shrink-0 flex-col items-center border-r border-border/50 py-4 gap-3">
          <button
            onClick={() => setPanelCollapsed(false)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            title={t('create.title')}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <FilePlus className="h-4 w-4 text-muted-foreground" />
        </div>
      ) : (
      <div className="flex w-[340px] shrink-0 flex-col border-r border-border/50">

        {/* Header -- fixed */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border/50 shrink-0">
          <div>
            <h1 className="text-sm font-semibold">{t('create.title')}</h1>
            <p className="text-[10px] text-muted-foreground">Isi detail untuk membuat dokumen</p>
          </div>
          <button onClick={() => setPanelCollapsed(true)} className="text-muted-foreground hover:text-foreground transition-colors">
            <ChevronLeft className="h-4 w-4" />
          </button>
        </div>

        {/* Form area -- takes 75% of remaining height, scrolls independently */}
        <div className="min-h-0 overflow-y-auto" style={{ flex: '3 1 0' }}>
          <div className="px-5 py-4 space-y-4">
              {/* Document Type -- always shown */}
              <FormField label="Document Type" required>
                <select
                  value={docType}
                  onChange={(e) => handleDocTypeChange(e.target.value as DocType)}
                  className={inputClass}
                >
                  <option value="generic">Generic Document</option>
                  <option value="nda">NDA</option>
                  <option value="sales">Sales Contract</option>
                  <option value="service">Service Contract</option>
                </select>
              </FormField>

              {/* Dynamic fields per type */}
              {docType === 'generic' && <GenericForm fields={fields} onChange={updateField} fieldErr={fieldErr} />}
              {docType === 'nda' && <NDAForm fields={fields} onChange={updateField} fieldErr={fieldErr} />}
              {(docType === 'sales' || docType === 'service') && <SalesServiceForm fields={fields} onChange={updateField} fieldErr={fieldErr} />}

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
                <DropZone onFileSelect={setReferenceFile} />
              </FormField>

              {/* Template */}
              <FormField label="Template Document (Optional)">
                <DropZone onFileSelect={setTemplateFile} />
              </FormField>

              {/* Generate button */}
              <div onClick={() => { if (!canGenerate) setShowErrors(true) }}>
                <Button className="w-full text-xs" disabled={!canGenerate} onClick={handleGenerate}>
                  {loading ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <FilePlus className="mr-2 h-3.5 w-3.5" />}
                  {loading ? 'Generating...' : generateLabel}
                </Button>
              </div>
              {showErrors && !canGenerate && (
                <p className="text-[10px] text-red-400">Please fill in all required fields marked with *</p>
              )}

              {error && <p className="text-xs text-red-400">{error}</p>}
            </div>
        </div>

        {/* History area -- takes 25% of remaining height, scrolls independently */}
        <div className="min-h-0 flex flex-col border-t border-border/50" style={{ flex: '1 1 0' }}>
          <div className="flex items-center justify-between px-5 py-2.5 shrink-0">
            <div className="flex items-center gap-1.5">
              <Clock className="h-3 w-3 text-muted-foreground" />
              <span className="text-[10px] font-semibold text-muted-foreground">Recent Documents</span>
            </div>
            <span className="text-[10px] text-primary cursor-pointer hover:underline">View all &rarr;</span>
          </div>
          <div className="flex-1 overflow-y-auto min-h-0">
            <div className="px-3 pb-2 space-y-0.5">
              {history.length === 0 ? (
                <p className="text-[10px] text-muted-foreground px-2 py-3">No documents generated yet</p>
              ) : history.map((item) => (
                <div key={item.id} className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted/50 transition-colors cursor-pointer">
                  <FileText className="h-4 w-4 shrink-0 text-primary/70" />
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-medium truncate">{item.title}</p>
                    <p className="text-[9px] text-muted-foreground">
                      <span className="text-primary/70">{(item.input_params as Record<string, string>).doc_type}</span> &middot; {formatTimeAgo(item.created_at)}
                    </p>
                  </div>
                  <CheckCircle className="h-3.5 w-3.5 shrink-0 text-green-400" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      )}

      {/* Column 3 -- Preview / results */}
      <div className="flex-1 flex flex-col overflow-y-auto">
        {result ? (
          <div className="p-8 space-y-6">
            <div>
              <h2 className="text-lg font-semibold">{result.title}</h2>
              <p className="text-xs text-muted-foreground mt-1">{result.summary}</p>
            </div>
            <div className="rounded-lg border border-border bg-secondary/30 p-6">
              <pre className="text-xs whitespace-pre-wrap font-sans leading-relaxed">{result.content}</pre>
            </div>
          </div>
        ) : (
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
        )}
      </div>
    </div>
  )
}
