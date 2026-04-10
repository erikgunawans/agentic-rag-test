import { useState } from 'react';
import { X, CloudUpload, ChevronDown, Calendar, FilePlus, FileText, CheckCircle2, Pencil, XCircle, Clock, ChevronRight } from 'lucide-react';
import { SubHeader, ActionButton, EmptyState, HistoryRow, SectionLabel } from './shared';

type DocumentType = 'generic' | 'nda' | 'sales' | 'service';

export function DocumentCreation() {
  const [documentType, setDocumentType] = useState<DocumentType>('generic');
  const [outputLanguage, setOutputLanguage] = useState<'both' | 'indonesian'>('both');
  const [refDropHover, setRefDropHover] = useState(false);
  const [templateDropHover, setTemplateDropHover] = useState(false);
  const [hoveredHistoryRow, setHoveredHistoryRow] = useState<number | null>(null);

  const documentTypes = [
    { value: 'generic', label: 'Generic Document' },
    { value: 'nda', label: 'NDA' },
    { value: 'sales', label: 'Sales Contract' },
    { value: 'service', label: 'Service Contract' }
  ];

  const recentDocuments = [
    { id: 1, name: 'NDA_Kerahasiaan_PT_Marina.pdf', type: 'NDA', time: 'Just now', status: 'done', fileType: 'pdf' },
    { id: 2, name: 'Kontrak_Distribusi_Q1.docx', type: 'Sales', time: '2h ago', status: 'done', fileType: 'docx' },
    { id: 3, name: 'Service_Agreement_Draft.docx', type: 'Service', time: 'Yesterday', status: 'draft', fileType: 'docx' },
    { id: 4, name: 'Generic_Compliance_Report.pdf', type: 'Generic', time: '2d ago', status: 'done', fileType: 'pdf' },
    { id: 5, name: 'NDA_Proyek_Ekspansi.docx', type: 'NDA', time: '3d ago', status: 'done', fileType: 'docx' },
    { id: 6, name: 'Sales_Contract_Retail.pdf', type: 'Sales', time: '4d ago', status: 'failed', fileType: 'pdf' },
    { id: 7, name: 'Perjanjian_Lisensi_SW.docx', type: 'Generic', time: '5d ago', status: 'done', fileType: 'docx' }
  ];

  const renderGenericForm = () => (
    <>
      <FormField label="Please specify document type" required>
        <input
          type="text"
          placeholder="e.g., Independent Contractor Agreement"
          className="form-input"
        />
      </FormField>

      <FormField label="First Party" required>
        <input type="text" placeholder="e.g., Buyer: John Doe" className="form-input" />
      </FormField>

      <FormField label="Second Party">
        <input type="text" placeholder="e.g., Seller: Jane Smith Inc." className="form-input" />
      </FormField>

      <FormField label="Effective Date">
        <div className="relative">
          <input type="text" placeholder="dd/mm/yyyy" className="form-input" />
          <Calendar
            size={14}
            style={{ position: 'absolute', right: '14px', top: '50%', transform: 'translateY(-50%)', color: '#475569' }}
          />
        </div>
      </FormField>

      <div>
        <div className="flex gap-2.5">
          <FormField label="Duration Count" className="w-[140px]">
            <input type="number" placeholder="e.g., 1" className="form-input" />
          </FormField>
          <FormField label="Duration Unit" className="flex-1">
            <select className="form-input">
              <option value="">Select an option</option>
              <option value="days">Days</option>
              <option value="months">Months</option>
              <option value="years">Years</option>
            </select>
          </FormField>
        </div>
      </div>

      <FormField label="Purpose of the document" required>
        <textarea
          placeholder="e.g., To define terms for software development services"
          className="form-textarea"
          style={{ minHeight: '88px' }}
        />
      </FormField>

      <FormField label="Scope of Work" required>
        <textarea
          placeholder="Detailed description of services/work"
          className="form-textarea"
          style={{ minHeight: '88px' }}
        />
      </FormField>

      <FormField label="Deliverables" required>
        <textarea
          placeholder="Specific outputs or results"
          className="form-textarea"
          style={{ minHeight: '88px' }}
        />
      </FormField>

      <FormField label="Payment Terms (Optional)">
        <input type="text" placeholder="e.g., Net 30 days, 50% upfront" className="form-input" />
      </FormField>

      <FormField label="Governing Law" required>
        <input type="text" defaultValue="Indonesia" className="form-input" />
      </FormField>

      <FormField label="Additional Notes or Specific Requirements">
        <textarea className="form-textarea" style={{ minHeight: '72px' }} />
      </FormField>
    </>
  );

  const renderNDAForm = () => (
    <>
      <FormField label="Disclosing Party" required>
        <input type="text" placeholder="e.g., Company A Inc." className="form-input" />
      </FormField>

      <FormField label="Receiving Party" required>
        <input type="text" placeholder="e.g., Consultant X LLC" className="form-input" />
      </FormField>

      <FormField label="Purpose of Disclosure" required>
        <textarea
          placeholder="e.g., Evaluation of potential business partnership"
          className="form-textarea"
          style={{ minHeight: '88px' }}
        />
      </FormField>

      <FormField label="Definition of Confidential Information" required>
        <textarea className="form-textarea" style={{ minHeight: '88px' }} />
      </FormField>

      <FormField label="Obligations of Receiving Party">
        <select className="form-input">
          <option value="">Select an option</option>
          <option value="standard">Standard confidentiality obligations</option>
          <option value="enhanced">Enhanced confidentiality obligations</option>
        </select>
      </FormField>

      <FormField label="Term of Agreement" required>
        <input type="text" placeholder="e.g., 5 years from effective date, indefinite" className="form-input" />
      </FormField>

      <FormField label="Return/Destruction of Confidential Information" required>
        <input type="text" placeholder="Upon termination or request" className="form-input" />
      </FormField>

      <FormField label="Governing Law" required>
        <input type="text" defaultValue="Indonesia" className="form-input" />
      </FormField>

      <FormField label="Additional Notes or Specific Requirements">
        <textarea className="form-textarea" style={{ minHeight: '72px' }} />
      </FormField>
    </>
  );

  const renderSalesContractForm = () => (
    <>
      <FormField label="First Party" required>
        <input type="text" placeholder="e.g., Buyer: John Doe" className="form-input" />
      </FormField>

      <FormField label="Second Party" required>
        <input type="text" placeholder="e.g., Seller: Jane Smith Inc." className="form-input" />
      </FormField>

      <FormField label="Effective Date" required>
        <div className="relative">
          <input type="text" placeholder="dd/mm/yyyy" className="form-input" />
          <Calendar
            size={14}
            style={{ position: 'absolute', right: '14px', top: '50%', transform: 'translateY(-50%)', color: '#475569' }}
          />
        </div>
      </FormField>

      <div>
        <div className="flex gap-2.5">
          <FormField label="Duration Count" required className="w-[140px]">
            <input type="number" placeholder="e.g., 1" className="form-input" />
          </FormField>
          <FormField label="Duration Unit" required className="flex-1">
            <select className="form-input">
              <option value="">Select an option</option>
              <option value="days">Days</option>
              <option value="months">Months</option>
              <option value="years">Years</option>
            </select>
          </FormField>
        </div>
      </div>

      <FormField label="Purpose of the document" required>
        <textarea className="form-textarea" style={{ minHeight: '88px' }} />
      </FormField>

      <FormField label="Scope of Work" required>
        <textarea className="form-textarea" style={{ minHeight: '88px' }} />
      </FormField>

      <FormField label="Deliverables" required>
        <textarea className="form-textarea" style={{ minHeight: '88px' }} />
      </FormField>

      <FormField label="Payment Terms (Optional)">
        <input type="text" className="form-input" />
      </FormField>

      <FormField label="Governing Law" required>
        <input type="text" defaultValue="Indonesia" className="form-input" />
      </FormField>

      <FormField label="Additional Notes or Specific Requirements">
        <textarea className="form-textarea" style={{ minHeight: '72px' }} />
      </FormField>
    </>
  );

  const getGenerateButtonLabel = () => {
    switch (documentType) {
      case 'nda':
        return 'Generate NDA';
      default:
        return 'Generate Draft';
    }
  };

  const getFileTypeConfig = (type: string) => {
    const configs = {
      pdf: { bg: 'rgba(248, 113, 113, 0.12)', color: '#F87171' },
      docx: { bg: 'rgba(34, 211, 238, 0.12)', color: '#22D3EE' },
      xlsx: { bg: 'rgba(52, 211, 153, 0.12)', color: '#34D399' }
    };
    return configs[type as keyof typeof configs] || configs.pdf;
  };

  const getStatusIcon = (status: string, isHovered: boolean) => {
    if (isHovered) {
      return <ChevronRight size={14} style={{ color: '#475569' }} />;
    }
    switch (status) {
      case 'done':
        return <CheckCircle2 size={14} style={{ color: '#34D399' }} />;
      case 'draft':
        return <Pencil size={14} style={{ color: '#94A3B8' }} />;
      case 'failed':
        return <XCircle size={14} style={{ color: '#F87171' }} />;
      default:
        return null;
    }
  };

  return (
    <>
      {/* Column 2 - Form Panel */}
      <div
        className="flex flex-col relative"
        style={{
          width: '360px',
          backgroundColor: '#0F1829',
          borderRight: '1px solid #1E2D45',
          height: '900px'
        }}
      >
        {/* SECTION 1 - FORM (676px fixed) */}
        <div
          className="flex flex-col"
          style={{
            height: '676px',
            flexShrink: 0
          }}
        >
          {/* Header - Fixed (64px) */}
          <div
            className="flex items-center justify-between px-5"
            style={{
              height: '64px',
              borderBottom: '1px solid #1E2D45',
              flexShrink: 0
            }}
          >
            <div className="flex flex-col gap-0.5">
              <div style={{ fontSize: '15px', fontWeight: 600, color: '#F1F5F9' }}>
                Create Document
              </div>
              <div style={{ fontSize: '11px', color: '#475569' }}>
                Fill in details to generate
              </div>
            </div>
            <button
              className="flex items-center justify-center rounded-lg transition-colors duration-200"
              style={{
                width: '28px',
                height: '28px',
                color: '#94A3B8'
              }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#1C2840')}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              <X size={14} />
            </button>
          </div>

          {/* Scrollable Form Body */}
          <div
            className="flex-1 overflow-y-auto custom-scrollbar"
          >
            <div className="px-5 pt-5 pb-3 flex flex-col gap-4">
              {/* Document Type Dropdown - Always First */}
              <FormField label="Document Type" required>
                <div className="relative">
                  <select
                    className="form-input"
                    value={documentType}
                    onChange={(e) => setDocumentType(e.target.value as DocumentType)}
                  >
                    {documentTypes.map((type) => (
                      <option key={type.value} value={type.value}>
                        {type.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown
                    size={14}
                    style={{
                      position: 'absolute',
                      right: '14px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: '#475569',
                      pointerEvents: 'none'
                    }}
                  />
                </div>
              </FormField>

              {/* Dynamic Form Based on Document Type */}
              {documentType === 'generic' && renderGenericForm()}
              {documentType === 'nda' && renderNDAForm()}
              {documentType === 'sales' && renderSalesContractForm()}
              {documentType === 'service' && renderSalesContractForm()}

              {/* Output Language Section */}
              <div className="mt-1">
                <div style={{ fontSize: '13px', fontWeight: 500, color: '#F1F5F9', marginBottom: '10px' }}>
                  Output Language
                </div>
                <div className="flex items-center gap-6">
                  <button
                    onClick={() => setOutputLanguage('both')}
                    className="flex items-center gap-2"
                  >
                    <div
                      className="flex items-center justify-center transition-all duration-150"
                      style={{
                        width: '18px',
                        height: '18px',
                        borderRadius: '50%',
                        border: outputLanguage === 'both' ? '2px solid #7C5CFC' : '2px solid #475569',
                        backgroundColor: 'transparent'
                      }}
                    >
                      {outputLanguage === 'both' && (
                        <div
                          style={{
                            width: '8px',
                            height: '8px',
                            borderRadius: '50%',
                            backgroundColor: '#7C5CFC'
                          }}
                        />
                      )}
                    </div>
                    <span style={{ fontSize: '13px', color: '#F1F5F9' }}>
                      English & Indonesian (Side-by-side)
                    </span>
                  </button>
                  <button
                    onClick={() => setOutputLanguage('indonesian')}
                    className="flex items-center gap-2"
                  >
                    <div
                      className="flex items-center justify-center transition-all duration-150"
                      style={{
                        width: '18px',
                        height: '18px',
                        borderRadius: '50%',
                        border: outputLanguage === 'indonesian' ? '2px solid #7C5CFC' : '2px solid #475569',
                        backgroundColor: 'transparent'
                      }}
                    >
                      {outputLanguage === 'indonesian' && (
                        <div
                          style={{
                            width: '8px',
                            height: '8px',
                            borderRadius: '50%',
                            backgroundColor: '#7C5CFC'
                          }}
                        />
                      )}
                    </div>
                    <span style={{ fontSize: '13px', color: outputLanguage === 'indonesian' ? '#F1F5F9' : '#94A3B8' }}>
                      Indonesian Only
                    </span>
                  </button>
                </div>
              </div>

              {/* Upload Reference Document */}
              <div>
                <div style={{ fontSize: '13px', fontWeight: 500, color: '#F1F5F9', marginBottom: '8px' }}>
                  Upload Reference Document (Optional)
                </div>
                <div
                  className="flex flex-col items-center justify-center p-5 rounded-xl transition-all duration-200"
                  style={{
                    minHeight: '100px',
                    backgroundColor: refDropHover ? 'rgba(124, 92, 252, 0.04)' : 'transparent',
                    border: refDropHover ? '1.5px dashed rgba(124, 92, 252, 0.5)' : '1.5px dashed rgba(100, 116, 139, 0.4)'
                  }}
                  onDragEnter={() => setRefDropHover(true)}
                  onDragLeave={() => setRefDropHover(false)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    setRefDropHover(false);
                  }}
                >
                  <CloudUpload size={28} style={{ color: '#475569', marginBottom: '6px' }} />
                  <div style={{ fontSize: '13px', color: '#475569', textAlign: 'center', marginBottom: '6px' }}>
                    Drop a file here, or{' '}
                    <span style={{ color: '#7C5CFC', textDecoration: 'underline', cursor: 'pointer' }}>
                      browse
                    </span>
                  </div>
                  <div style={{ fontSize: '11px', color: '#475569', textAlign: 'center' }}>
                    Accepted formats: .txt, .docx, .pdf
                  </div>
                  <div style={{ fontSize: '11px', color: '#475569', textAlign: 'center' }}>
                    up to 50 Mb
                  </div>
                </div>
              </div>

              {/* Upload Template Document */}
              <div>
                <div style={{ fontSize: '13px', fontWeight: 500, color: '#F1F5F9', marginBottom: '8px' }}>
                  Upload Template Document (Optional)
                </div>
                <div
                  className="flex flex-col items-center justify-center p-5 rounded-xl transition-all duration-200"
                  style={{
                    minHeight: '100px',
                    backgroundColor: templateDropHover ? 'rgba(124, 92, 252, 0.04)' : 'transparent',
                    border: templateDropHover ? '1.5px dashed rgba(124, 92, 252, 0.5)' : '1.5px dashed rgba(100, 116, 139, 0.4)'
                  }}
                  onDragEnter={() => setTemplateDropHover(true)}
                  onDragLeave={() => setTemplateDropHover(false)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    setTemplateDropHover(false);
                  }}
                >
                  <CloudUpload size={28} style={{ color: '#475569', marginBottom: '6px' }} />
                  <div style={{ fontSize: '13px', color: '#475569', textAlign: 'center', marginBottom: '6px' }}>
                    Drop a file here, or{' '}
                    <span style={{ color: '#7C5CFC', textDecoration: 'underline', cursor: 'pointer' }}>
                      browse
                    </span>
                  </div>
                  <div style={{ fontSize: '11px', color: '#475569', textAlign: 'center' }}>
                    Accepted formats: .txt, .docx, .pdf
                  </div>
                  <div style={{ fontSize: '11px', color: '#475569', textAlign: 'center' }}>
                    up to 50 Mb
                  </div>
                </div>
              </div>

              {/* Separator Line */}
              <div
                style={{
                  height: '1px',
                  background: 'linear-gradient(to right, transparent, #1E2D45, transparent)',
                  marginTop: '12px'
                }}
              />

              {/* Generate Button */}
              <div className="px-5 mt-3 mb-3">
                <button
                  className="w-full flex items-center justify-center rounded-xl transition-all duration-200"
                  style={{
                    height: '44px',
                    backgroundColor: '#7C5CFC',
                    fontSize: '14px',
                    fontWeight: 600,
                    color: 'white'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = '#8B6EFD';
                    e.currentTarget.style.boxShadow = '0 4px 20px rgba(124, 92, 252, 0.4)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = '#7C5CFC';
                    e.currentTarget.style.boxShadow = 'none';
                  }}
                >
                  {getGenerateButtonLabel()}
                </button>
              </div>
            </div>

            {/* Bottom Fade Overlay */}
            <div
              className="absolute bottom-0 left-0 right-0 pointer-events-none"
              style={{
                height: '40px',
                background: 'linear-gradient(to top, #0F1829, transparent)'
              }}
            />
          </div>
        </div>

        {/* DIVIDER (always at 676px) */}
        <div style={{ width: '100%', height: '1px', backgroundColor: '#1E2D45', flexShrink: 0 }} />

        {/* SECTION 2 - DOCUMENT HISTORY (223px fixed) */}
        <div
          className="flex flex-col"
          style={{
            height: '223px',
            backgroundColor: '#0F1829',
            flexShrink: 0
          }}
        >
          {/* Sub-header - Fixed (40px) */}
          <div
            className="flex items-center justify-between px-4"
            style={{
              height: '40px',
              borderBottom: '1px solid #1E2D45',
              flexShrink: 0
            }}
          >
            <div className="flex items-center gap-1.5">
              <Clock size={14} style={{ color: '#475569' }} />
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#94A3B8' }}>
                Recent Documents
              </div>
            </div>
            <button
              className="transition-colors duration-150"
              style={{ fontSize: '11px', color: '#475569' }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#94A3B8')}
              onMouseLeave={(e) => (e.currentTarget.style.color = '#475569')}
            >
              View all →
            </button>
          </div>

          {/* Scrollable History List (184px) */}
          <div
            className="flex-1 overflow-y-auto custom-scrollbar"
            style={{
              height: '184px'
            }}
          >
            {recentDocuments.map((doc) => {
              const fileConfig = getFileTypeConfig(doc.fileType);
              const isHovered = hoveredHistoryRow === doc.id;
              return (
                <button
                  key={doc.id}
                  className="w-full flex items-center gap-2.5 px-4 transition-colors duration-150"
                  style={{
                    height: '44px',
                    backgroundColor: isHovered ? '#1C2840' : 'transparent',
                    cursor: 'pointer'
                  }}
                  onMouseEnter={() => setHoveredHistoryRow(doc.id)}
                  onMouseLeave={() => setHoveredHistoryRow(null)}
                >
                  {/* File Icon Badge */}
                  <div
                    className="flex items-center justify-center"
                    style={{
                      width: '30px',
                      height: '30px',
                      backgroundColor: fileConfig.bg,
                      borderRadius: '8px',
                      flexShrink: 0
                    }}
                  >
                    <FileText size={13} style={{ color: fileConfig.color }} />
                  </div>

                  {/* Text Stack */}
                  <div className="flex-1 flex flex-col gap-0.5 items-start min-w-0">
                    <div
                      style={{
                        fontSize: '12px',
                        fontWeight: 500,
                        color: '#F1F5F9',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        width: '100%'
                      }}
                    >
                      {doc.name}
                    </div>
                    <div className="flex items-center gap-1.5">
                      <div
                        style={{
                          fontSize: '10px',
                          color: '#475569',
                          backgroundColor: '#162033',
                          padding: '1px 6px',
                          borderRadius: '4px'
                        }}
                      >
                        {doc.type}
                      </div>
                      <div
                        style={{
                          width: '3px',
                          height: '3px',
                          borderRadius: '50%',
                          backgroundColor: '#475569'
                        }}
                      />
                      <div style={{ fontSize: '10px', color: '#475569' }}>{doc.time}</div>
                    </div>
                  </div>

                  {/* Status Icon */}
                  <div style={{ flexShrink: 0 }}>{getStatusIcon(doc.status, isHovered)}</div>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Column 3 - Main Area (Empty State) */}
      <EmptyState
        icon={FilePlus}
        line1="Fill in the form on the left to generate"
        line2="your document and preview it here"
        hintChips={[
          { color: '#F87171', label: 'PDF format' },
          { color: '#22D3EE', label: 'DOCX format' },
          { color: '#34D399', label: 'Bilingual' }
        ]}
      />

      <style>{`
        .custom-scrollbar {
          scrollbar-width: thin;
          scrollbar-color: rgba(124, 92, 252, 0.25) transparent;
        }

        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }

        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }

        .custom-scrollbar::-webkit-scrollbar-thumb {
          background-color: rgba(124, 92, 252, 0.25);
          border-radius: 4px;
        }

        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background-color: rgba(124, 92, 252, 0.45);
        }

        .form-input {
          width: 100%;
          height: 40px;
          padding: 0 14px;
          background-color: #162033;
          border: 1px solid #1e2d45;
          border-radius: 10px;
          font-size: 13px;
          color: #f1f5f9;
          outline: none;
          transition: all 0.15s;
          appearance: none;
        }

        .form-input::placeholder {
          color: #475569;
        }

        .form-input:hover {
          border-color: rgba(124, 92, 252, 0.25);
        }

        .form-input:focus {
          border-color: rgba(124, 92, 252, 0.4);
          box-shadow: 0 0 0 3px rgba(124, 92, 252, 0.12);
        }

        .form-textarea {
          width: 100%;
          padding: 12px 14px;
          background-color: #162033;
          border: 1px solid #1e2d45;
          border-radius: 10px;
          font-size: 13px;
          color: #f1f5f9;
          outline: none;
          resize: vertical;
          transition: all 0.15s;
          font-family: inherit;
        }

        .form-textarea::placeholder {
          color: #475569;
        }

        .form-textarea:hover {
          border-color: rgba(124, 92, 252, 0.25);
        }

        .form-textarea:focus {
          border-color: rgba(124, 92, 252, 0.4);
          box-shadow: 0 0 0 3px rgba(124, 92, 252, 0.12);
        }

        select.form-input {
          cursor: pointer;
        }
      `}</style>
    </>
  );
}

interface FormFieldProps {
  label: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}

function FormField({ label, required, children, className }: FormFieldProps) {
  return (
    <div className={className}>
      <label style={{ fontSize: '13px', fontWeight: 500, color: '#F1F5F9', marginBottom: '6px', display: 'block' }}>
        {label}
        {required && <span style={{ color: '#F87171', marginLeft: '2px' }}>*</span>}
      </label>
      {children}
    </div>
  );
}