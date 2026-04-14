import { useState, useEffect } from 'react'
import { FilePlus, ChevronLeft, PanelLeftClose, Clock, CheckCircle, XCircle, Loader2, FileText, Menu, Plus, BookmarkPlus } from 'lucide-react'
import { useToolHistory, formatTimeAgo } from '@/hooks/useToolHistory'
import { useSidebar } from '@/hooks/useSidebar'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { DropZone } from '@/components/shared/DropZone'
import { EmptyState } from '@/components/shared/EmptyState'
import { apiFetch } from '@/lib/api'
import { ConfidenceBadge } from '@/components/shared/ConfidenceBadge'

type DocType = 'generic' | 'nda' | 'sales' | 'service' | 'vendor' | 'jv' | 'property_lease' | 'employment' | 'sop_resolution'

interface Clause {
  id: string
  title: string
  content: string
  category: string
  applicable_doc_types: string[]
  risk_level: string
  is_global: boolean
}

interface Template {
  id: string
  name: string
  doc_type: string
  default_values: Record<string, string>
  default_clauses: string[]
  is_global: boolean
}

interface ClauseRisk {
  clause_title: string
  risk_level: string
  risk_note: string
}

interface GeneratedDocument {
  title: string
  content: string
  summary: string
  confidence_score?: number
  review_status?: string
  clause_risks?: ClauseRisk[]
}

const RISK_STYLE: Record<string, { color: string; bg: string }> = {
  high: { color: 'text-red-400', bg: 'border-red-500/30 bg-red-500/5' },
  medium: { color: 'text-amber-400', bg: 'border-amber-500/30 bg-amber-500/5' },
  low: { color: 'text-green-400', bg: 'border-green-500/30 bg-green-500/5' },
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

function VendorForm({ fields, onChange, fieldErr }: { fields: Record<string, string>; onChange: (key: string, val: string) => void; fieldErr: (k: string) => boolean }) {
  return (
    <>
      <FormField label="Vendor Name" required error={fieldErr('vendor_name')}>
        <input className={fieldErr('vendor_name') ? inputErrorClass : inputClass} placeholder="e.g., PT Supplier Utama" value={fields.vendor_name || ''} onChange={(e) => onChange('vendor_name', e.target.value)} />
      </FormField>
      <FormField label="Client Name" required error={fieldErr('client_name')}>
        <input className={fieldErr('client_name') ? inputErrorClass : inputClass} placeholder="e.g., PT Pembeli Sejahtera" value={fields.client_name || ''} onChange={(e) => onChange('client_name', e.target.value)} />
      </FormField>
      <FormField label="Effective Date" required error={fieldErr('effective_date')}>
        <Input type="date" className={`text-xs bg-secondary ${fieldErr('effective_date') ? 'border-red-500/50' : ''}`} value={fields.effective_date || ''} onChange={(e) => onChange('effective_date', e.target.value)} />
      </FormField>
      <FormField label="Scope of Supply" required error={fieldErr('scope_of_supply')}>
        <textarea className={fieldErr('scope_of_supply') ? textareaErrorClass : textareaClass} placeholder="Describe the goods/services to be supplied" value={fields.scope_of_supply || ''} onChange={(e) => onChange('scope_of_supply', e.target.value)} />
      </FormField>
      <FormField label="Payment Terms" required error={fieldErr('payment_terms')}>
        <input className={fieldErr('payment_terms') ? inputErrorClass : inputClass} placeholder="e.g., Net 30 days" value={fields.payment_terms || ''} onChange={(e) => onChange('payment_terms', e.target.value)} />
      </FormField>
      <FormField label="Delivery Terms">
        <input className={inputClass} placeholder="e.g., FOB Destination" value={fields.delivery_terms || ''} onChange={(e) => onChange('delivery_terms', e.target.value)} />
      </FormField>
      <FormField label="Warranty Period">
        <input className={inputClass} placeholder="e.g., 12 months" value={fields.warranty_period || ''} onChange={(e) => onChange('warranty_period', e.target.value)} />
      </FormField>
      <FormField label="Governing Law" required error={fieldErr('governing_law')}>
        <input className={fieldErr('governing_law') ? inputErrorClass : inputClass} value={fields.governing_law || 'Indonesia'} onChange={(e) => onChange('governing_law', e.target.value)} />
      </FormField>
    </>
  )
}

function JVForm({ fields, onChange, fieldErr }: { fields: Record<string, string>; onChange: (key: string, val: string) => void; fieldErr: (k: string) => boolean }) {
  return (
    <>
      <FormField label="Party A" required error={fieldErr('party_a')}>
        <input className={fieldErr('party_a') ? inputErrorClass : inputClass} placeholder="e.g., PT Alpha Investasi" value={fields.party_a || ''} onChange={(e) => onChange('party_a', e.target.value)} />
      </FormField>
      <FormField label="Party B" required error={fieldErr('party_b')}>
        <input className={fieldErr('party_b') ? inputErrorClass : inputClass} placeholder="e.g., PT Beta Mitra" value={fields.party_b || ''} onChange={(e) => onChange('party_b', e.target.value)} />
      </FormField>
      <FormField label="Joint Venture Name" required error={fieldErr('jv_name')}>
        <input className={fieldErr('jv_name') ? inputErrorClass : inputClass} placeholder="e.g., PT Alpha-Beta Bersama" value={fields.jv_name || ''} onChange={(e) => onChange('jv_name', e.target.value)} />
      </FormField>
      <FormField label="Purpose" required error={fieldErr('purpose')}>
        <textarea className={fieldErr('purpose') ? textareaErrorClass : textareaClass} placeholder="Describe the purpose of the joint venture" value={fields.purpose || ''} onChange={(e) => onChange('purpose', e.target.value)} />
      </FormField>
      <FormField label="Capital Contribution" required error={fieldErr('capital_contribution')}>
        <input className={fieldErr('capital_contribution') ? inputErrorClass : inputClass} placeholder="e.g., Party A: 60%, Party B: 40%" value={fields.capital_contribution || ''} onChange={(e) => onChange('capital_contribution', e.target.value)} />
      </FormField>
      <FormField label="Profit Sharing">
        <input className={inputClass} placeholder="e.g., Pro-rata based on capital contribution" value={fields.profit_sharing || ''} onChange={(e) => onChange('profit_sharing', e.target.value)} />
      </FormField>
      <div className="grid grid-cols-[1fr_1fr] gap-2.5">
        <FormField label="Duration Count">
          <input type="number" className={inputClass} placeholder="e.g., 5" value={fields.duration_count || ''} onChange={(e) => onChange('duration_count', e.target.value)} />
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
      <FormField label="Governing Law" required error={fieldErr('governing_law')}>
        <input className={fieldErr('governing_law') ? inputErrorClass : inputClass} value={fields.governing_law || 'Indonesia'} onChange={(e) => onChange('governing_law', e.target.value)} />
      </FormField>
    </>
  )
}

function PropertyLeaseForm({ fields, onChange, fieldErr }: { fields: Record<string, string>; onChange: (key: string, val: string) => void; fieldErr: (k: string) => boolean }) {
  return (
    <>
      <FormField label="Lessor" required error={fieldErr('lessor')}>
        <input className={fieldErr('lessor') ? inputErrorClass : inputClass} placeholder="e.g., PT Properti Jaya" value={fields.lessor || ''} onChange={(e) => onChange('lessor', e.target.value)} />
      </FormField>
      <FormField label="Lessee" required error={fieldErr('lessee')}>
        <input className={fieldErr('lessee') ? inputErrorClass : inputClass} placeholder="e.g., PT Tenant Utama" value={fields.lessee || ''} onChange={(e) => onChange('lessee', e.target.value)} />
      </FormField>
      <FormField label="Property Address" required error={fieldErr('property_address')}>
        <textarea className={fieldErr('property_address') ? textareaErrorClass : textareaClass} placeholder="Full property address" value={fields.property_address || ''} onChange={(e) => onChange('property_address', e.target.value)} />
      </FormField>
      <FormField label="Lease Term" required error={fieldErr('lease_term')}>
        <input className={fieldErr('lease_term') ? inputErrorClass : inputClass} placeholder="e.g., 2 years" value={fields.lease_term || ''} onChange={(e) => onChange('lease_term', e.target.value)} />
      </FormField>
      <FormField label="Monthly Rent" required error={fieldErr('monthly_rent')}>
        <input className={fieldErr('monthly_rent') ? inputErrorClass : inputClass} placeholder="e.g., Rp 50.000.000" value={fields.monthly_rent || ''} onChange={(e) => onChange('monthly_rent', e.target.value)} />
      </FormField>
      <FormField label="Deposit">
        <input className={inputClass} placeholder="e.g., 3 months rent" value={fields.deposit || ''} onChange={(e) => onChange('deposit', e.target.value)} />
      </FormField>
      <FormField label="Purpose of Use">
        <input className={inputClass} placeholder="e.g., Office space" value={fields.purpose_of_use || ''} onChange={(e) => onChange('purpose_of_use', e.target.value)} />
      </FormField>
      <FormField label="Governing Law" required error={fieldErr('governing_law')}>
        <input className={fieldErr('governing_law') ? inputErrorClass : inputClass} value={fields.governing_law || 'Indonesia'} onChange={(e) => onChange('governing_law', e.target.value)} />
      </FormField>
    </>
  )
}

function EmploymentForm({ fields, onChange, fieldErr }: { fields: Record<string, string>; onChange: (key: string, val: string) => void; fieldErr: (k: string) => boolean }) {
  return (
    <>
      <FormField label="Employer" required error={fieldErr('employer')}>
        <input className={fieldErr('employer') ? inputErrorClass : inputClass} placeholder="e.g., PT Perusahaan Maju" value={fields.employer || ''} onChange={(e) => onChange('employer', e.target.value)} />
      </FormField>
      <FormField label="Employee" required error={fieldErr('employee')}>
        <input className={fieldErr('employee') ? inputErrorClass : inputClass} placeholder="e.g., Budi Santoso" value={fields.employee || ''} onChange={(e) => onChange('employee', e.target.value)} />
      </FormField>
      <FormField label="Position" required error={fieldErr('position')}>
        <input className={fieldErr('position') ? inputErrorClass : inputClass} placeholder="e.g., Senior Software Engineer" value={fields.position || ''} onChange={(e) => onChange('position', e.target.value)} />
      </FormField>
      <FormField label="Start Date" required error={fieldErr('start_date')}>
        <Input type="date" className={`text-xs bg-secondary ${fieldErr('start_date') ? 'border-red-500/50' : ''}`} value={fields.start_date || ''} onChange={(e) => onChange('start_date', e.target.value)} />
      </FormField>
      <FormField label="Salary" required error={fieldErr('salary')}>
        <input className={fieldErr('salary') ? inputErrorClass : inputClass} placeholder="e.g., Rp 25.000.000/month" value={fields.salary || ''} onChange={(e) => onChange('salary', e.target.value)} />
      </FormField>
      <FormField label="Probation Period">
        <input className={inputClass} placeholder="e.g., 3 months" value={fields.probation_period || ''} onChange={(e) => onChange('probation_period', e.target.value)} />
      </FormField>
      <FormField label="Working Hours">
        <input className={inputClass} placeholder="e.g., 40 hours/week" value={fields.working_hours || ''} onChange={(e) => onChange('working_hours', e.target.value)} />
      </FormField>
      <FormField label="Benefits">
        <textarea className={`${inputClass} min-h-[64px] resize-none`} placeholder="e.g., Health insurance, annual leave, etc." value={fields.benefits || ''} onChange={(e) => onChange('benefits', e.target.value)} />
      </FormField>
      <FormField label="Termination Notice" required error={fieldErr('termination_notice')}>
        <input className={fieldErr('termination_notice') ? inputErrorClass : inputClass} placeholder="e.g., 30 days written notice" value={fields.termination_notice || ''} onChange={(e) => onChange('termination_notice', e.target.value)} />
      </FormField>
      <FormField label="Governing Law" required error={fieldErr('governing_law')}>
        <input className={fieldErr('governing_law') ? inputErrorClass : inputClass} value={fields.governing_law || 'Indonesia'} onChange={(e) => onChange('governing_law', e.target.value)} />
      </FormField>
    </>
  )
}

function SOPResolutionForm({ fields, onChange, fieldErr }: { fields: Record<string, string>; onChange: (key: string, val: string) => void; fieldErr: (k: string) => boolean }) {
  return (
    <>
      <FormField label="Company Name" required error={fieldErr('company_name')}>
        <input className={fieldErr('company_name') ? inputErrorClass : inputClass} placeholder="e.g., PT Perusahaan Utama" value={fields.company_name || ''} onChange={(e) => onChange('company_name', e.target.value)} />
      </FormField>
      <FormField label="Resolution Type" required error={fieldErr('resolution_type')}>
        <select className={fieldErr('resolution_type') ? inputErrorClass : inputClass} value={fields.resolution_type || ''} onChange={(e) => onChange('resolution_type', e.target.value)}>
          <option value="">Select type</option>
          <option value="circular">Circular Resolution</option>
          <option value="meeting">Meeting Resolution</option>
        </select>
      </FormField>
      <FormField label="Resolution Date" required error={fieldErr('resolution_date')}>
        <Input type="date" className={`text-xs bg-secondary ${fieldErr('resolution_date') ? 'border-red-500/50' : ''}`} value={fields.resolution_date || ''} onChange={(e) => onChange('resolution_date', e.target.value)} />
      </FormField>
      <FormField label="Subject Matter" required error={fieldErr('subject_matter')}>
        <input className={fieldErr('subject_matter') ? inputErrorClass : inputClass} placeholder="e.g., Appointment of new director" value={fields.subject_matter || ''} onChange={(e) => onChange('subject_matter', e.target.value)} />
      </FormField>
      <FormField label="Resolved Items" required error={fieldErr('resolved_items')}>
        <textarea className={fieldErr('resolved_items') ? textareaErrorClass : textareaClass} placeholder="List the items resolved" value={fields.resolved_items || ''} onChange={(e) => onChange('resolved_items', e.target.value)} />
      </FormField>
      <FormField label="Board Members">
        <input className={inputClass} placeholder="e.g., John Doe, Jane Smith" value={fields.board_members || ''} onChange={(e) => onChange('board_members', e.target.value)} />
      </FormField>
      <FormField label="Governing Law" required error={fieldErr('governing_law')}>
        <input className={fieldErr('governing_law') ? inputErrorClass : inputClass} value={fields.governing_law || 'Indonesia'} onChange={(e) => onChange('governing_law', e.target.value)} />
      </FormField>
    </>
  )
}

// --- Recent documents ---

// --- Main page ---
export function DocumentCreationPage() {
  const { t } = useI18n()
  const { history, reload: reloadHistory } = useToolHistory('create')
  const { panelCollapsed, togglePanel } = useSidebar()
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false)
  const [docType, setDocType] = useState<DocType>('generic')
  const [outputLang, setOutputLang] = useState<'both' | 'indonesian'>('both')
  const [fields, setFields] = useState<Record<string, string>>({})
  const [referenceFile, setReferenceFile] = useState<File | null>(null)
  const [templateFile, setTemplateFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<GeneratedDocument | null>(null)
  const [showErrors, setShowErrors] = useState(false)

  const [selectedClauses, setSelectedClauses] = useState<Clause[]>([])
  const [clausePickerOpen, setClausePickerOpen] = useState(false)
  const [availableClauses, setAvailableClauses] = useState<Clause[]>([])
  const [templates, setTemplates] = useState<Template[]>([])
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch(`/clause-library?doc_type=${docType}&limit=30`).then(r => r.json()),
      apiFetch(`/document-templates?doc_type=${docType}&limit=20`).then(r => r.json()),
    ]).then(([clauseData, tplData]) => {
      setAvailableClauses(clauseData.data || [])
      setTemplates(tplData.data || [])
    }).catch(() => {})
  }, [docType])

  function updateField(key: string, value: string) {
    setFields((prev) => ({ ...prev, [key]: value }))
  }

  function handleDocTypeChange(newType: DocType) {
    setDocType(newType)
    setFields({})
    setShowErrors(false)
    setSelectedTemplateId(null)
  }

  async function handleTemplateSelect(templateId: string) {
    if (!templateId) { setSelectedTemplateId(null); return }
    setSelectedTemplateId(templateId)
    try {
      const res = await apiFetch(`/document-templates/${templateId}`)
      const data = await res.json()
      if (data.template?.default_values) {
        setFields(prev => ({ ...data.template.default_values, ...prev }))
      }
      if (data.clauses?.length) {
        setSelectedClauses(prev => {
          const existingIds = new Set(prev.map(c => c.id))
          return [...prev, ...data.clauses.filter((c: Clause) => !existingIds.has(c.id))]
        })
      }
    } catch {}
  }

  async function handleSaveAsTemplate() {
    const name = prompt('Template name:')
    if (!name) return
    try {
      await apiFetch('/document-templates', {
        method: 'POST',
        body: JSON.stringify({ name, doc_type: docType, default_values: fields, default_clauses: selectedClauses.map(c => c.id) }),
      })
      const res = await apiFetch(`/document-templates?doc_type=${docType}&limit=20`)
      const d = await res.json()
      setTemplates(d.data || [])
    } catch (err) { alert(err instanceof Error ? err.message : 'Failed') }
  }

  async function handleGenerate() {
    setLoading(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('doc_type', docType)
      formData.append('fields', JSON.stringify(fields))
      formData.append('output_language', outputLang)
      formData.append('clause_ids', JSON.stringify(selectedClauses.map(c => c.id)))
      if (selectedTemplateId) formData.append('template_id', selectedTemplateId)
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
    vendor: ['vendor_name', 'client_name', 'effective_date', 'scope_of_supply', 'payment_terms', 'governing_law'],
    jv: ['party_a', 'party_b', 'jv_name', 'purpose', 'capital_contribution', 'governing_law'],
    property_lease: ['lessor', 'lessee', 'property_address', 'lease_term', 'monthly_rent', 'governing_law'],
    employment: ['employer', 'employee', 'position', 'start_date', 'salary', 'termination_notice', 'governing_law'],
    sop_resolution: ['company_name', 'resolution_type', 'resolution_date', 'subject_matter', 'resolved_items', 'governing_law'],
  }
  const canGenerate = !loading && REQUIRED_FIELDS[docType].every((key) => fields[key]?.trim())
  function fieldErr(key: string): boolean {
    return showErrors && REQUIRED_FIELDS[docType].includes(key) && !fields[key]?.trim()
  }

  const generateLabel = docType === 'nda' ? 'Generate NDA' : 'Generate Draft'

  // Clause selector section (reusable for both panels)
  const clauseSelectorSection = (
    <div className="space-y-2.5">
      <label className="text-xs font-medium">Clauses</label>
      {/* Selected clause chips */}
      {selectedClauses.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selectedClauses.map((clause) => {
            const style = RISK_STYLE[clause.risk_level] || RISK_STYLE.medium
            const mismatch = !clause.is_global && !clause.applicable_doc_types.includes(docType)
            return (
              <div key={clause.id} className={`flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] ${style.bg} ${mismatch ? 'opacity-60' : ''}`}>
                <span className={`font-semibold ${style.color}`}>{clause.risk_level?.charAt(0).toUpperCase()}</span>
                <span className="truncate max-w-[120px]">{clause.title}</span>
                {mismatch && <span className="text-amber-400 text-[9px]" title="Clause may not apply to this doc type">!</span>}
                <button onClick={() => setSelectedClauses(prev => prev.filter(c => c.id !== clause.id))} className="ml-0.5 text-muted-foreground hover:text-foreground">
                  <XCircle className="h-3 w-3" />
                </button>
              </div>
            )
          })}
        </div>
      )}
      {/* Add Clause button */}
      <button
        onClick={() => setClausePickerOpen(!clausePickerOpen)}
        className="flex items-center gap-1 text-[10px] text-primary hover:underline"
      >
        <Plus className="h-3 w-3" />
        {clausePickerOpen ? 'Close' : 'Add Clause'}
      </button>
      {/* Clause picker inline list */}
      {clausePickerOpen && (
        <div className="rounded-lg border border-border bg-secondary/50 p-2 max-h-[160px] overflow-y-auto space-y-1">
          {availableClauses.filter(c => !selectedClauses.some(sc => sc.id === c.id)).length === 0 ? (
            <p className="text-[10px] text-muted-foreground px-1">No more clauses available</p>
          ) : (
            availableClauses.filter(c => !selectedClauses.some(sc => sc.id === c.id)).map((clause) => {
              const style = RISK_STYLE[clause.risk_level] || RISK_STYLE.medium
              return (
                <button
                  key={clause.id}
                  onClick={() => { setSelectedClauses(prev => [...prev, clause]); }}
                  className="flex items-center gap-2 w-full rounded-md px-2 py-1.5 hover:bg-muted/50 transition-colors text-left"
                >
                  <span className={`text-[9px] font-bold uppercase ${style.color}`}>{clause.risk_level}</span>
                  <span className="text-[10px] truncate flex-1">{clause.title}</span>
                  <span className="text-[9px] text-muted-foreground">{clause.category}</span>
                </button>
              )
            })
          )}
        </div>
      )}
    </div>
  )

  // Template selector section (reusable for both panels)
  const templateSelectorSection = templates.length > 0 ? (
    <FormField label="Template">
      <select
        value={selectedTemplateId || ''}
        onChange={(e) => handleTemplateSelect(e.target.value)}
        className={inputClass}
      >
        <option value="">Select a template...</option>
        {templates.map((tpl) => (
          <option key={tpl.id} value={tpl.id}>{tpl.name}</option>
        ))}
      </select>
    </FormField>
  ) : null

  // Doc type select options (reusable)
  const docTypeOptions = (
    <>
      <option value="generic">Generic Document</option>
      <option value="nda">NDA</option>
      <option value="sales">Sales Contract</option>
      <option value="service">Service Contract</option>
      <option value="vendor">Vendor Agreement</option>
      <option value="jv">Joint Venture Agreement</option>
      <option value="property_lease">Property Lease</option>
      <option value="employment">Employment Contract</option>
      <option value="sop_resolution">SOP / Resolution</option>
    </>
  )

  // Dynamic form fields based on doc type (reusable)
  const dynamicFormFields = (
    <>
      {docType === 'generic' && <GenericForm fields={fields} onChange={updateField} fieldErr={fieldErr} />}
      {docType === 'nda' && <NDAForm fields={fields} onChange={updateField} fieldErr={fieldErr} />}
      {(docType === 'sales' || docType === 'service') && <SalesServiceForm fields={fields} onChange={updateField} fieldErr={fieldErr} />}
      {docType === 'vendor' && <VendorForm fields={fields} onChange={updateField} fieldErr={fieldErr} />}
      {docType === 'jv' && <JVForm fields={fields} onChange={updateField} fieldErr={fieldErr} />}
      {docType === 'property_lease' && <PropertyLeaseForm fields={fields} onChange={updateField} fieldErr={fieldErr} />}
      {docType === 'employment' && <EmploymentForm fields={fields} onChange={updateField} fieldErr={fieldErr} />}
      {docType === 'sop_resolution' && <SOPResolutionForm fields={fields} onChange={updateField} fieldErr={fieldErr} />}
    </>
  )

  return (
    <div className="flex h-full">
      {/* Mobile panel trigger */}
      <button
        onClick={() => setMobilePanelOpen(true)}
        className="md:hidden fixed bottom-4 right-4 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg focus-ring"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Mobile panel overlay */}
      {mobilePanelOpen && (
        <div className="md:hidden fixed inset-0 z-40">
          <div className="mobile-backdrop" onClick={() => setMobilePanelOpen(false)} />
          <div className="mobile-panel bg-background border-r border-border/50 overflow-y-auto">
            {/* Header -- fixed */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-border/50 shrink-0">
              <div>
                <h1 className="text-sm font-semibold">{t('create.title')}</h1>
                <p className="text-[10px] text-muted-foreground">Isi detail untuk membuat dokumen</p>
              </div>
              <button onClick={() => setMobilePanelOpen(false)} className="text-muted-foreground hover:text-foreground transition-colors focus-ring">
                <ChevronLeft className="h-4 w-4" />
              </button>
            </div>

            {/* Form area */}
            <div className="min-h-0 overflow-y-auto" style={{ flex: '3 1 0' }}>
              <div className="px-5 py-4 space-y-4">
                {templateSelectorSection}

                <FormField label="Document Type" required>
                  <select
                    value={docType}
                    onChange={(e) => handleDocTypeChange(e.target.value as DocType)}
                    className={inputClass}
                  >
                    {docTypeOptions}
                  </select>
                </FormField>

                {dynamicFormFields}

                {clauseSelectorSection}

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

                <FormField label="Reference Document (Optional)">
                  <DropZone onFileSelect={setReferenceFile} />
                </FormField>

                <FormField label="Template Document (Optional)">
                  <DropZone onFileSelect={setTemplateFile} />
                </FormField>

                <div onClick={() => { if (!canGenerate) setShowErrors(true) }}>
                  <Button className="w-full text-xs" disabled={!canGenerate} onClick={handleGenerate}>
                    {loading ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <FilePlus className="mr-2 h-3.5 w-3.5" />}
                    {loading ? 'Generating...' : generateLabel}
                  </Button>
                </div>
                <Button variant="ghost" size="sm" className="w-full text-xs text-muted-foreground" onClick={handleSaveAsTemplate}>
                  <BookmarkPlus className="mr-1.5 h-3 w-3" /> Save as Template
                </Button>
                {showErrors && !canGenerate && (
                  <p className="text-[10px] text-red-400">Please fill in all required fields marked with *</p>
                )}

                {error && <p className="text-xs text-red-400">{error}</p>}
              </div>
            </div>

            {/* History area */}
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
        </div>
      )}

      {/* Column 2 -- Form (top 75%) + History (bottom 25%) */}
      {!panelCollapsed && (
      <div className="hidden md:flex w-[340px] shrink-0 flex-col border-r border-border/50 bg-sidebar">

        {/* Header -- fixed */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border/50 shrink-0">
          <div>
            <h1 className="text-sm font-semibold">{t('create.title')}</h1>
            <p className="text-[10px] text-muted-foreground">Isi detail untuk membuat dokumen</p>
          </div>
          <button onClick={togglePanel} className="flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors focus-ring" title="Collapse sidebar">
            <PanelLeftClose className="h-4 w-4" />
          </button>
        </div>

        {/* Form area -- takes 75% of remaining height, scrolls independently */}
        <div className="min-h-0 overflow-y-auto" style={{ flex: '3 1 0' }}>
          <div className="px-5 py-4 space-y-4">
              {templateSelectorSection}

              {/* Document Type -- always shown */}
              <FormField label="Document Type" required>
                <select
                  value={docType}
                  onChange={(e) => handleDocTypeChange(e.target.value as DocType)}
                  className={inputClass}
                >
                  {docTypeOptions}
                </select>
              </FormField>

              {/* Dynamic fields per type */}
              {dynamicFormFields}

              {/* Clause selector */}
              {clauseSelectorSection}

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
              <Button variant="ghost" size="sm" className="w-full text-xs text-muted-foreground" onClick={handleSaveAsTemplate}>
                <BookmarkPlus className="mr-1.5 h-3 w-3" /> Save as Template
              </Button>
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
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-semibold">{result.title}</h2>
                {result.confidence_score != null && (
                  <ConfidenceBadge score={result.confidence_score} reviewStatus={result.review_status} />
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-1">{result.summary}</p>
            </div>
            {result.clause_risks && result.clause_risks.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Clause Risk Assessment</h3>
                {result.clause_risks.map((cr: ClauseRisk, i: number) => {
                  const style = RISK_STYLE[cr.risk_level] || RISK_STYLE.medium
                  return (
                    <div key={i} className={`rounded-lg border p-3 ${style.bg}`}>
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-semibold">{cr.clause_title}</span>
                        <span className={`text-[10px] uppercase font-bold ${style.color}`}>{cr.risk_level}</span>
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-1">{cr.risk_note}</p>
                    </div>
                  )
                })}
              </div>
            )}
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
