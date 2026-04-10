import { ChevronDown, Calendar, User, Building2, FileText, Clock, DollarSign, Shield } from 'lucide-react';

export function FormVariantsReference() {
  const formVariants = [
    {
      type: 'Generic Document',
      fields: [
        { label: 'Document Title', placeholder: 'Enter document title', icon: FileText },
        { label: 'Description', placeholder: 'Brief description of the document', type: 'textarea', rows: 3 },
        { label: 'Category', placeholder: 'Select category', type: 'select', icon: FileText },
        { label: 'Tags', placeholder: 'Add tags (comma separated)', icon: FileText },
        { label: 'Author', placeholder: 'Document author', icon: User },
        { label: 'Created Date', placeholder: 'Select date', type: 'date', icon: Calendar },
        { label: 'Status', placeholder: 'Select status', type: 'select', icon: FileText },
        { label: 'Notes', placeholder: 'Additional notes', type: 'textarea', rows: 4 }
      ]
    },
    {
      type: 'NDA',
      fields: [
        { label: 'Agreement Title', placeholder: 'NDA title', icon: Shield },
        { label: 'Disclosing Party', placeholder: 'Company or individual name', icon: Building2 },
        { label: 'Receiving Party', placeholder: 'Company or individual name', icon: Building2 },
        { label: 'Effective Date', placeholder: 'Select date', type: 'date', icon: Calendar },
        { label: 'Expiration Date', placeholder: 'Select date', type: 'date', icon: Calendar },
        { label: 'Jurisdiction', placeholder: 'Legal jurisdiction', icon: Building2 },
        { label: 'Confidentiality Level', placeholder: 'Select level', type: 'select', icon: Shield },
        { label: 'Special Terms', placeholder: 'Additional confidentiality terms', type: 'textarea', rows: 4 }
      ]
    },
    {
      type: 'Sales Contract',
      fields: [
        { label: 'Contract Title', placeholder: 'Sales agreement title', icon: FileText },
        { label: 'Buyer Name', placeholder: 'Buyer company or individual', icon: Building2 },
        { label: 'Seller Name', placeholder: 'Seller company or individual', icon: Building2 },
        { label: 'Contract Value', placeholder: 'Total contract amount', icon: DollarSign },
        { label: 'Payment Terms', placeholder: 'Payment schedule and terms', type: 'textarea', rows: 3 },
        { label: 'Delivery Date', placeholder: 'Expected delivery date', type: 'date', icon: Calendar },
        { label: 'Contract Duration', placeholder: 'Duration in months', icon: Clock },
        { label: 'Terms & Conditions', placeholder: 'Additional terms', type: 'textarea', rows: 4 }
      ]
    },
    {
      type: 'Service Contract',
      fields: [
        { label: 'Service Agreement Title', placeholder: 'Service contract title', icon: FileText },
        { label: 'Service Provider', placeholder: 'Provider company name', icon: Building2 },
        { label: 'Client Name', placeholder: 'Client company or individual', icon: Building2 },
        { label: 'Service Description', placeholder: 'Describe services provided', type: 'textarea', rows: 3 },
        { label: 'Start Date', placeholder: 'Service start date', type: 'date', icon: Calendar },
        { label: 'End Date', placeholder: 'Service end date', type: 'date', icon: Calendar },
        { label: 'Service Fee', placeholder: 'Monthly or total fee', icon: DollarSign },
        { label: 'Payment Schedule', placeholder: 'Payment frequency', type: 'select', icon: DollarSign },
        { label: 'SLA Terms', placeholder: 'Service level agreement terms', type: 'textarea', rows: 3 }
      ]
    }
  ];

  return (
    <div 
      className="flex gap-6 p-8 overflow-x-auto" 
      style={{ 
        backgroundColor: '#0B1120',
        minHeight: '100vh'
      }}
    >
      {formVariants.map((variant, variantIdx) => (
        <div
          key={variantIdx}
          className="flex flex-col rounded-2xl overflow-hidden"
          style={{
            width: '360px',
            height: '900px',
            backgroundColor: '#0F1829',
            border: '1px solid #1E2D45',
            flexShrink: 0
          }}
        >
          {/* Header */}
          <div
            className="flex items-center justify-center"
            style={{
              height: '64px',
              borderBottom: '1px solid #1E2D45',
              backgroundColor: '#162033'
            }}
          >
            <div style={{ fontSize: '15px', fontWeight: 600, color: '#F1F5F9' }}>
              {variant.type}
            </div>
          </div>

          {/* Form Content */}
          <div className="flex-1 overflow-y-auto p-5" style={{ backgroundColor: '#0F1829' }}>
            <style>
              {`
                .form-scroll-${variantIdx}::-webkit-scrollbar {
                  width: 4px;
                }
                .form-scroll-${variantIdx}::-webkit-scrollbar-track {
                  background: transparent;
                }
                .form-scroll-${variantIdx}::-webkit-scrollbar-thumb {
                  background: rgba(124, 92, 252, 0.25);
                  border-radius: 4px;
                }
                .form-scroll-${variantIdx}::-webkit-scrollbar-thumb:hover {
                  background: rgba(124, 92, 252, 0.45);
                }
              `}
            </style>

            <div className={`flex flex-col gap-4 form-scroll-${variantIdx}`}>
              {/* Document Type Dropdown - Always First */}
              <div className="flex flex-col gap-2">
                <label style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
                  Document Type
                </label>
                <div
                  className="flex items-center justify-between px-3 rounded-[10px]"
                  style={{
                    height: '40px',
                    backgroundColor: '#162033',
                    border: '1px solid rgba(124, 92, 252, 0.4)',
                    boxShadow: '0 0 0 3px rgba(124, 92, 252, 0.15)'
                  }}
                >
                  <div className="flex items-center gap-2">
                    <FileText size={16} style={{ color: '#7C5CFC' }} />
                    <span style={{ fontSize: '13px', color: '#F1F5F9' }}>
                      {variant.type}
                    </span>
                  </div>
                  <ChevronDown size={16} style={{ color: '#7C5CFC' }} />
                </div>
              </div>

              {/* Dynamic Fields Based on Type */}
              {variant.fields.map((field, fieldIdx) => {
                const FieldIcon = field.icon;
                
                return (
                  <div key={fieldIdx} className="flex flex-col gap-2">
                    <label style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
                      {field.label}
                    </label>

                    {field.type === 'textarea' ? (
                      <textarea
                        placeholder={field.placeholder}
                        rows={field.rows || 3}
                        className="px-3 py-2.5 rounded-[10px] bg-transparent border outline-none resize-none transition-all duration-200"
                        style={{
                          backgroundColor: '#162033',
                          border: '1px solid #1E2D45',
                          fontSize: '13px',
                          color: '#F1F5F9',
                          lineHeight: 1.5
                        }}
                        onFocus={(e) => {
                          e.currentTarget.style.borderColor = 'rgba(124, 92, 252, 0.4)';
                          e.currentTarget.style.boxShadow = '0 0 0 3px rgba(124, 92, 252, 0.15)';
                        }}
                        onBlur={(e) => {
                          e.currentTarget.style.borderColor = '#1E2D45';
                          e.currentTarget.style.boxShadow = 'none';
                        }}
                      />
                    ) : field.type === 'select' ? (
                      <div
                        className="flex items-center justify-between px-3 rounded-[10px] cursor-pointer transition-all duration-200"
                        style={{
                          height: '40px',
                          backgroundColor: '#162033',
                          border: '1px solid #1E2D45'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.borderColor = 'rgba(124, 92, 252, 0.4)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.borderColor = '#1E2D45';
                        }}
                      >
                        <div className="flex items-center gap-2">
                          {FieldIcon && <FieldIcon size={16} style={{ color: '#475569' }} />}
                          <span style={{ fontSize: '13px', color: '#475569' }}>
                            {field.placeholder}
                          </span>
                        </div>
                        <ChevronDown size={16} style={{ color: '#475569' }} />
                      </div>
                    ) : field.type === 'date' ? (
                      <div
                        className="flex items-center gap-2 px-3 rounded-[10px] transition-all duration-200"
                        style={{
                          height: '40px',
                          backgroundColor: '#162033',
                          border: '1px solid #1E2D45'
                        }}
                      >
                        {FieldIcon && <FieldIcon size={16} style={{ color: '#475569' }} />}
                        <input
                          type="text"
                          placeholder={field.placeholder}
                          className="flex-1 bg-transparent border-none outline-none"
                          style={{ fontSize: '13px', color: '#475569' }}
                          onFocus={(e) => {
                            e.currentTarget.parentElement!.style.borderColor = 'rgba(124, 92, 252, 0.4)';
                            e.currentTarget.parentElement!.style.boxShadow = '0 0 0 3px rgba(124, 92, 252, 0.15)';
                          }}
                          onBlur={(e) => {
                            e.currentTarget.parentElement!.style.borderColor = '#1E2D45';
                            e.currentTarget.parentElement!.style.boxShadow = 'none';
                          }}
                        />
                      </div>
                    ) : (
                      <div
                        className="flex items-center gap-2 px-3 rounded-[10px] transition-all duration-200"
                        style={{
                          height: '40px',
                          backgroundColor: '#162033',
                          border: '1px solid #1E2D45'
                        }}
                      >
                        {FieldIcon && <FieldIcon size={16} style={{ color: '#475569' }} />}
                        <input
                          type="text"
                          placeholder={field.placeholder}
                          className="flex-1 bg-transparent border-none outline-none"
                          style={{ fontSize: '13px', color: '#475569' }}
                          onFocus={(e) => {
                            e.currentTarget.parentElement!.style.borderColor = 'rgba(124, 92, 252, 0.4)';
                            e.currentTarget.parentElement!.style.boxShadow = '0 0 0 3px rgba(124, 92, 252, 0.15)';
                          }}
                          onBlur={(e) => {
                            e.currentTarget.parentElement!.style.borderColor = '#1E2D45';
                            e.currentTarget.parentElement!.style.boxShadow = 'none';
                          }}
                        />
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Action Buttons */}
              <div className="flex flex-col gap-2 mt-4 pt-4" style={{ borderTop: '1px solid #1E2D45' }}>
                <button
                  className="flex items-center justify-center rounded-[10px] transition-all duration-200"
                  style={{
                    height: '40px',
                    backgroundColor: '#7C5CFC',
                    fontSize: '13px',
                    fontWeight: 600,
                    color: 'white'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = '#8B6EFD';
                    e.currentTarget.style.boxShadow = '0 4px 16px rgba(124, 92, 252, 0.4)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = '#7C5CFC';
                    e.currentTarget.style.boxShadow = 'none';
                  }}
                >
                  Generate Document
                </button>
                <button
                  className="flex items-center justify-center rounded-[10px] transition-all duration-200"
                  style={{
                    height: '40px',
                    backgroundColor: 'transparent',
                    border: '1px solid #1E2D45',
                    fontSize: '13px',
                    fontWeight: 600,
                    color: '#94A3B8'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'rgba(124, 92, 252, 0.4)';
                    e.currentTarget.style.color = '#F1F5F9';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = '#1E2D45';
                    e.currentTarget.style.color = '#94A3B8';
                  }}
                >
                  Save as Draft
                </button>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
