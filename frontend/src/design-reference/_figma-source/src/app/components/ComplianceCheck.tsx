import { useState } from 'react';
import { Info, CloudUpload, ChevronDown, FileText, CheckCircle2, XCircle, Clock, ChevronRight, ShieldCheck, ShieldAlert, ShieldX, Shield } from 'lucide-react';

type ComplianceFramework = 'ojk' | 'international' | 'gdpr' | 'custom';
type CheckScope = 'legal' | 'risk' | 'missing' | 'regulatory';
type ComplianceStatus = 'pass' | 'fail' | 'review';

interface UploadedFile {
  name: string;
  size: string;
  type: 'pdf' | 'docx' | 'txt';
}

export function ComplianceCheck() {
  const [uploadedDoc, setUploadedDoc] = useState<UploadedFile | null>(null);
  const [uploadHover, setUploadHover] = useState(false);
  const [framework, setFramework] = useState<ComplianceFramework>('ojk');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [activeScopes, setActiveScopes] = useState<CheckScope[]>(['legal', 'risk', 'missing', 'regulatory']);
  const [additionalContext, setAdditionalContext] = useState('');
  const [hoveredHistoryRow, setHoveredHistoryRow] = useState<number | null>(null);
  const [contextFocused, setContextFocused] = useState(false);

  const frameworks = [
    { value: 'ojk' as ComplianceFramework, label: 'Indonesian Law (OJK / UU PT)' },
    { value: 'international' as ComplianceFramework, label: 'International Contract Standards' },
    { value: 'gdpr' as ComplianceFramework, label: 'GDPR / Data Privacy' },
    { value: 'custom' as ComplianceFramework, label: 'Custom Framework' }
  ];

  const scopes = [
    { value: 'legal' as CheckScope, label: 'Legal Clauses' },
    { value: 'risk' as CheckScope, label: 'Risk Flags' },
    { value: 'missing' as CheckScope, label: 'Missing Terms' },
    { value: 'regulatory' as CheckScope, label: 'Regulatory' }
  ];

  const complianceHistory = [
    { id: 1, doc: 'NDA_Kerahasiaan_PT_Marina.pdf', framework: 'OJK', time: '1h ago', status: 'pass' as ComplianceStatus },
    { id: 2, doc: 'Kontrak_Distribusi_Q1.docx', framework: 'OJK', time: '3h ago', status: 'review' as ComplianceStatus },
    { id: 3, doc: 'Compliance_Report_Q1.pdf', framework: 'Intl', time: 'Yesterday', status: 'pass' as ComplianceStatus },
    { id: 4, doc: 'Service_Agreement_Draft.docx', framework: 'GDPR', time: '2d ago', status: 'fail' as ComplianceStatus },
    { id: 5, doc: 'License_Agreement_v2.pdf', framework: 'OJK', time: '3d ago', status: 'pass' as ComplianceStatus },
    { id: 6, doc: 'Payment_Terms_Draft.docx', framework: 'Intl', time: '4d ago', status: 'review' as ComplianceStatus }
  ];

  const getFileTypeConfig = (type: string) => {
    const configs = {
      pdf: { bg: 'rgba(248, 113, 113, 0.12)', color: '#F87171' },
      docx: { bg: 'rgba(34, 211, 238, 0.12)', color: '#22D3EE' },
      txt: { bg: 'rgba(148, 163, 184, 0.12)', color: '#94A3B8' }
    };
    return configs[type as keyof typeof configs] || configs.pdf;
  };

  const getStatusConfig = (status: ComplianceStatus) => {
    const configs = {
      pass: { 
        bg: 'rgba(52, 211, 153, 0.12)', 
        color: '#34D399', 
        icon: ShieldCheck,
        label: 'Passed' 
      },
      fail: { 
        bg: 'rgba(248, 113, 113, 0.12)', 
        color: '#F87171', 
        icon: ShieldX,
        label: 'Failed' 
      },
      review: { 
        bg: 'rgba(245, 158, 11, 0.12)', 
        color: '#F59E0B', 
        icon: ShieldAlert,
        label: 'Review' 
      }
    };
    return configs[status];
  };

  const toggleScope = (scope: CheckScope) => {
    if (activeScopes.includes(scope)) {
      setActiveScopes(activeScopes.filter(s => s !== scope));
    } else {
      setActiveScopes([...activeScopes, scope]);
    }
  };

  const isRunEnabled = uploadedDoc !== null;

  return (
    <>
      {/* Column 2 - Compliance Panel */}
      <div
        className="flex flex-col"
        style={{
          width: '360px',
          backgroundColor: '#0F1829',
          borderRight: '1px solid #1E2D45',
          height: '900px'
        }}
      >
        {/* TOP SECTION - Upload Panel (676px fixed) */}
        <div
          className="flex flex-col relative"
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
                Compliance Check
              </div>
              <div style={{ fontSize: '11px', color: '#475569' }}>
                Upload a document to check compliance
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
              <Info size={14} />
            </button>
          </div>

          {/* Scrollable Body */}
          <div
            className="overflow-y-auto p-5 custom-scrollbar"
            style={{
              position: 'absolute',
              top: '64px',
              left: 0,
              right: 0,
              bottom: '56px',
              height: '556px'
            }}
          >
            <div className="flex flex-col gap-5">
              {/* Document Upload */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <ShieldCheck size={16} style={{ color: '#7C5CFC' }} />
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
                    Document to Check
                  </div>
                  <div style={{ fontSize: '11px', color: '#475569', marginLeft: 'auto' }}>
                    (Required)
                  </div>
                </div>

                {uploadedDoc === null ? (
                  <div
                    className="flex flex-col items-center justify-center transition-all duration-200"
                    style={{
                      height: '160px',
                      backgroundColor: uploadHover ? 'rgba(124, 92, 252, 0.05)' : '#162033',
                      border: uploadHover 
                        ? '1.5px dashed rgba(124, 92, 252, 0.6)' 
                        : '1.5px dashed rgba(100, 116, 139, 0.4)',
                      borderRadius: '14px',
                      padding: '20px',
                      gap: '8px',
                      cursor: 'pointer',
                      boxShadow: uploadHover ? '0 0 24px rgba(124, 92, 252, 0.12)' : 'none'
                    }}
                    onDragEnter={() => setUploadHover(true)}
                    onDragLeave={() => setUploadHover(false)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      setUploadHover(false);
                      setUploadedDoc({ name: 'NDA_Kerahasiaan_PT_Marina.pdf', size: '2.4 MB', type: 'pdf' });
                    }}
                    onClick={() => setUploadedDoc({ name: 'NDA_Kerahasiaan_PT_Marina.pdf', size: '2.4 MB', type: 'pdf' })}
                  >
                    <div
                      className="flex items-center justify-center transition-all duration-200"
                      style={{
                        width: '44px',
                        height: '44px',
                        borderRadius: '50%',
                        backgroundColor: uploadHover ? 'rgba(124, 92, 252, 0.18)' : 'rgba(124, 92, 252, 0.10)',
                        border: '1px solid rgba(124, 92, 252, 0.15)'
                      }}
                    >
                      <ShieldCheck size={22} style={{ color: '#7C5CFC' }} />
                    </div>
                    <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9', textAlign: 'center' }}>
                      Drag & drop your document here
                    </div>
                    <div style={{ fontSize: '12px', color: '#475569', textAlign: 'center' }}>
                      or{' '}
                      <span style={{ color: '#7C5CFC', textDecoration: 'underline' }}>
                        browse files
                      </span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#475569', textAlign: 'center' }}>
                      PDF, DOCX, TXT up to 50MB
                    </div>
                  </div>
                ) : (
                  <div
                    className="flex items-center gap-3"
                    style={{
                      height: '80px',
                      padding: '0 16px',
                      backgroundColor: 'rgba(52, 211, 153, 0.05)',
                      border: '1.5px solid rgba(52, 211, 153, 0.35)',
                      borderRadius: '14px'
                    }}
                  >
                    <div
                      className="flex items-center justify-center"
                      style={{
                        width: '40px',
                        height: '40px',
                        borderRadius: '10px',
                        backgroundColor: getFileTypeConfig(uploadedDoc.type).bg,
                        flexShrink: 0
                      }}
                    >
                      <FileText size={18} style={{ color: getFileTypeConfig(uploadedDoc.type).color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div
                        style={{
                          fontSize: '13px',
                          fontWeight: 500,
                          color: '#F1F5F9',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          marginBottom: '3px'
                        }}
                      >
                        {uploadedDoc.name}
                      </div>
                      <div style={{ fontSize: '11px', color: '#475569' }}>
                        {uploadedDoc.size} · {uploadedDoc.type.toUpperCase()} · Ready for check
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 size={16} style={{ color: '#34D399' }} />
                      <button
                        onClick={() => setUploadedDoc(null)}
                        className="transition-colors duration-150"
                        style={{ color: '#475569' }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = '#F87171')}
                        onMouseLeave={(e) => (e.currentTarget.style.color = '#475569')}
                      >
                        <XCircle size={14} />
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Compliance Framework */}
              <div>
                <div style={{ fontSize: '13px', fontWeight: 500, color: '#F1F5F9', marginBottom: '8px' }}>
                  Compliance Framework
                </div>
                <div className="relative">
                  <button
                    onClick={() => setDropdownOpen(!dropdownOpen)}
                    className="w-full flex items-center justify-between transition-all duration-150"
                    style={{
                      height: '40px',
                      padding: '0 14px',
                      backgroundColor: '#162033',
                      border: dropdownOpen ? '1px solid rgba(124, 92, 252, 0.4)' : '1px solid #1E2D45',
                      borderRadius: '10px',
                      fontSize: '13px',
                      color: '#F1F5F9',
                      boxShadow: dropdownOpen ? '0 0 0 3px rgba(124, 92, 252, 0.15)' : 'none'
                    }}
                    onMouseEnter={(e) => {
                      if (!dropdownOpen) {
                        e.currentTarget.style.borderColor = 'rgba(124, 92, 252, 0.25)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!dropdownOpen) {
                        e.currentTarget.style.borderColor = '#1E2D45';
                      }
                    }}
                  >
                    <span>{frameworks.find(f => f.value === framework)?.label}</span>
                    <ChevronDown size={14} style={{ color: '#475569' }} />
                  </button>

                  {dropdownOpen && (
                    <div
                      className="absolute top-full left-0 right-0 mt-1 z-10"
                      style={{
                        backgroundColor: '#162033',
                        border: '1px solid #1E2D45',
                        borderRadius: '10px',
                        overflow: 'hidden',
                        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)'
                      }}
                    >
                      {frameworks.map((fw) => (
                        <button
                          key={fw.value}
                          onClick={() => {
                            setFramework(fw.value);
                            setDropdownOpen(false);
                          }}
                          className="w-full flex items-center transition-colors duration-150"
                          style={{
                            height: '36px',
                            padding: '0 14px',
                            fontSize: '13px',
                            color: '#F1F5F9',
                            backgroundColor: framework === fw.value ? '#1C2840' : 'transparent'
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#1C2840')}
                          onMouseLeave={(e) => {
                            if (framework !== fw.value) {
                              e.currentTarget.style.backgroundColor = 'transparent';
                            }
                          }}
                        >
                          {fw.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Check Scope */}
              <div>
                <div style={{ fontSize: '13px', fontWeight: 500, color: '#F1F5F9', marginBottom: '8px' }}>
                  Check Scope
                </div>
                <div className="flex flex-wrap gap-2">
                  {scopes.map((scope) => {
                    const isActive = activeScopes.includes(scope.value);
                    return (
                      <button
                        key={scope.value}
                        onClick={() => toggleScope(scope.value)}
                        className="transition-all duration-150"
                        style={{
                          height: '30px',
                          padding: '0 12px',
                          borderRadius: '20px',
                          backgroundColor: isActive ? 'rgba(124, 92, 252, 0.12)' : '#162033',
                          border: isActive ? '1px solid rgba(124, 92, 252, 0.4)' : '1px solid #1E2D45',
                          fontSize: '12px',
                          fontWeight: 500,
                          color: isActive ? '#7C5CFC' : '#94A3B8'
                        }}
                        onMouseEnter={(e) => {
                          if (!isActive) {
                            e.currentTarget.style.borderColor = 'rgba(124, 92, 252, 0.3)';
                            e.currentTarget.style.color = '#F1F5F9';
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (!isActive) {
                            e.currentTarget.style.borderColor = '#1E2D45';
                            e.currentTarget.style.color = '#94A3B8';
                          }
                        }}
                      >
                        {scope.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Additional Context */}
              <div>
                <div style={{ fontSize: '13px', fontWeight: 500, color: '#F1F5F9', marginBottom: '8px' }}>
                  Additional Context (Optional)
                </div>
                <textarea
                  value={additionalContext}
                  onChange={(e) => setAdditionalContext(e.target.value)}
                  onFocus={() => setContextFocused(true)}
                  onBlur={() => setContextFocused(false)}
                  placeholder="e.g., Focus on payment clauses and termination conditions..."
                  className="w-full bg-transparent border outline-none resize-none transition-all duration-150"
                  style={{
                    minHeight: '80px',
                    padding: '12px 14px',
                    backgroundColor: '#162033',
                    border: contextFocused ? '1px solid rgba(124, 92, 252, 0.4)' : '1px solid #1E2D45',
                    borderRadius: '10px',
                    fontSize: '12px',
                    color: '#F1F5F9',
                    lineHeight: 1.5,
                    boxShadow: contextFocused ? '0 0 0 3px rgba(124, 92, 252, 0.12)' : 'none'
                  }}
                />
              </div>
            </div>

            {/* Bottom fade overlay */}
            <div
              className="absolute bottom-0 left-0 right-0 pointer-events-none"
              style={{
                height: '40px',
                background: 'linear-gradient(to top, #0F1829, transparent)'
              }}
            />
          </div>

          {/* Sticky Run Button (56px) */}
          <div
            style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              height: '56px',
              backgroundColor: '#0F1829',
              flexShrink: 0
            }}
          >
            {/* Separator Line */}
            <div
              style={{
                height: '1px',
                background: 'linear-gradient(to right, transparent, #1E2D45, transparent)',
                marginTop: '8px'
              }}
            />

            {/* Button */}
            <div className="px-5 mt-3 mb-3">
              <button
                className="w-full flex items-center justify-center gap-2 rounded-xl transition-all duration-200"
                disabled={!isRunEnabled}
                style={{
                  height: '44px',
                  backgroundColor: isRunEnabled ? '#7C5CFC' : '#162033',
                  border: isRunEnabled ? 'none' : '1px solid #1E2D45',
                  fontSize: '14px',
                  fontWeight: 600,
                  color: isRunEnabled ? 'white' : '#475569',
                  cursor: isRunEnabled ? 'pointer' : 'not-allowed'
                }}
                onMouseEnter={(e) => {
                  if (isRunEnabled) {
                    e.currentTarget.style.backgroundColor = '#8B6EFD';
                    e.currentTarget.style.boxShadow = '0 4px 20px rgba(124, 92, 252, 0.4)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (isRunEnabled) {
                    e.currentTarget.style.backgroundColor = '#7C5CFC';
                    e.currentTarget.style.boxShadow = 'none';
                  }
                }}
              >
                {isRunEnabled ? (
                  <>
                    <ShieldCheck size={16} />
                    Run Compliance Check
                  </>
                ) : (
                  <>
                    <Shield size={16} />
                    Upload a Document First
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Column 3 - Main Area (Empty State) */}
      <div
        className="flex-1 flex items-center justify-center relative overflow-hidden"
        style={{ backgroundColor: '#0B1120' }}
      >
        {/* Mesh Gradients */}
        <div
          className="absolute top-0 right-0 pointer-events-none"
          style={{
            width: '600px',
            height: '600px',
            background: 'radial-gradient(circle, rgba(76, 29, 149, 0.06) 0%, transparent 70%)'
          }}
        />
        <div
          className="absolute bottom-0 left-0 pointer-events-none"
          style={{
            width: '500px',
            height: '500px',
            background: 'radial-gradient(circle, rgba(10, 31, 61, 0.3) 0%, transparent 70%)'
          }}
        />

        {/* Empty State Content */}
        <div className="flex flex-col items-center gap-4 relative z-10">
          {/* Nested circles */}
          <div
            className="flex items-center justify-center rounded-full"
            style={{
              width: '96px',
              height: '96px',
              backgroundColor: 'rgba(124, 92, 252, 0.06)',
              border: '1px solid rgba(124, 92, 252, 0.12)'
            }}
          >
            <div
              className="flex items-center justify-center rounded-full"
              style={{
                width: '72px',
                height: '72px',
                backgroundColor: 'rgba(124, 92, 252, 0.10)',
                border: '1px solid rgba(124, 92, 252, 0.18)'
              }}
            >
              <ShieldCheck size={32} style={{ color: 'rgba(124, 92, 252, 0.5)' }} />
            </div>
          </div>

          {/* Body text - 2 lines */}
          <div className="flex flex-col items-center gap-1">
            <div
              style={{
                fontSize: '14px',
                color: '#475569',
                textAlign: 'center',
                maxWidth: '340px',
                lineHeight: 1.6
              }}
            >
              Upload a document and run a compliance check
            </div>
            <div
              style={{
                fontSize: '14px',
                color: '#475569',
                textAlign: 'center',
                maxWidth: '340px',
                lineHeight: 1.6
              }}
            >
              to see detailed results here
            </div>
          </div>

          {/* Hint chips - 3 chips */}
          <div className="flex items-center gap-2">
            {[
              { color: '#34D399', label: 'Passed clauses' },
              { color: '#F87171', label: 'Failed checks' },
              { color: '#F59E0B', label: 'Needs review' }
            ].map((chip, index) => (
              <div
                key={index}
                className="flex items-center gap-1.5"
                style={{
                  height: '26px',
                  padding: '0 10px',
                  borderRadius: '20px',
                  backgroundColor: '#162033',
                  border: '1px solid #1E2D45',
                  fontSize: '11px',
                  color: '#475569'
                }}
              >
                <div
                  style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    backgroundColor: chip.color
                  }}
                />
                {chip.label}
              </div>
            ))}
          </div>
        </div>
      </div>

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
      `}</style>
    </>
  );
}