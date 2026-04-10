import { useState } from 'react';
import {
  Info,
  FileSearch,
  CheckCircle2,
  XCircle,
  ChevronDown,
  Clock,
  FileCheck,
  FileWarning,
  FileX,
  ChevronRight,
  Scale
} from 'lucide-react';
import { SubHeader, HistoryRow, DropZone, ActionButton, HintChipRow, SectionLabel } from './shared';

export function ContractAnalysis() {
  const [uploadedFile, setUploadedFile] = useState<{
    name: string;
    size: string;
    type: 'pdf' | 'docx';
  } | null>(null);
  const [dropZoneHover, setDropZoneHover] = useState(false);
  const [activeAnalysisTypes, setActiveAnalysisTypes] = useState({
    risk: true,
    obligations: true,
    clauses: true,
    terms: true
  });
  const [governingLaw, setGoverningLaw] = useState('Indonesia');
  const [analysisDepth, setAnalysisDepth] = useState<'Quick' | 'Standard' | 'Deep'>('Quick');
  const [hoveredHistoryRow, setHoveredHistoryRow] = useState<number | null>(null);
  const [lawDropdownOpen, setLawDropdownOpen] = useState(false);

  const analysisTypes = [
    { key: 'risk', label: 'Risk Assessment' },
    { key: 'obligations', label: 'Key Obligations' },
    { key: 'clauses', label: 'Critical Clauses' },
    { key: 'terms', label: 'Missing Terms' }
  ];

  const depthOptions = ['Quick', 'Standard', 'Deep'] as const;

  const lawOptions = ['Indonesia', 'International', 'Singapore Law', 'Custom / Other'];

  const historyRows = [
    { id: 1, name: 'NDA_PT_Marina_2026.pdf', depth: 'Standard', time: '1h ago', risk: 'Low' },
    { id: 2, name: 'Kontrak_Distribusi_Q1.docx', depth: 'Deep', time: '3h ago', risk: 'High' },
    { id: 3, name: 'Service_Agreement_Draft.docx', depth: 'Quick', time: 'Yesterday', risk: 'Med' },
    { id: 4, name: 'Perjanjian_Lisensi_SW.pdf', depth: 'Standard', time: '2d ago', risk: 'Low' },
    { id: 5, name: 'Sales_Contract_Retail.docx', depth: 'Deep', time: '3d ago', risk: 'High' },
    { id: 6, name: 'Employment_Contract_v2.pdf', depth: 'Standard', time: '4d ago', risk: 'Med' }
  ];

  const getRiskConfig = (risk: string) => {
    const configs = {
      Low: { bg: 'rgba(52, 211, 153, 0.12)', color: '#34D399', icon: FileCheck, label: 'Low Risk' },
      Med: { bg: 'rgba(245, 158, 11, 0.12)', color: '#F59E0B', icon: FileWarning, label: 'Med Risk' },
      High: { bg: 'rgba(248, 113, 113, 0.12)', color: '#F87171', icon: FileX, label: 'High Risk' }
    };
    return configs[risk as keyof typeof configs] || configs.Low;
  };

  const handleFileUpload = () => {
    // Simulate file upload
    setUploadedFile({
      name: 'Commercial_Agreement_Draft.pdf',
      size: '3.2',
      type: 'pdf'
    });
  };

  return (
    <>
      {/* Column 2 - Contract Analysis Panel */}
      <div
        className="flex flex-col"
        style={{
          width: '360px',
          backgroundColor: '#0F1829',
          borderRight: '1px solid #1E2D45',
          height: '900px',
          position: 'relative'
        }}
      >
        {/* TOP SECTION - Upload + Options Panel (676px fixed) */}
        <div
          className="flex flex-col"
          style={{
            height: '676px',
            flexShrink: 0
          }}
        >
          {/* Header (64px, fixed) */}
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
                Contract Analysis
              </div>
              <div style={{ fontSize: '11px', color: '#475569' }}>
                Upload a contract to analyze
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
            className="flex-1 overflow-y-auto px-5 py-5 contract-analysis-scroll"
            style={{
              position: 'relative'
            }}
          >
            <style>
              {`
                .contract-analysis-scroll::-webkit-scrollbar {
                  width: 4px;
                }
                .contract-analysis-scroll::-webkit-scrollbar-track {
                  background: transparent;
                }
                .contract-analysis-scroll::-webkit-scrollbar-thumb {
                  background: rgba(124, 92, 252, 0.25);
                  border-radius: 4px;
                }
                .contract-analysis-scroll::-webkit-scrollbar-thumb:hover {
                  background: rgba(124, 92, 252, 0.45);
                }
              `}
            </style>
            <div className="flex flex-col gap-5">
              {/* Document Upload Area */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <FileSearch size={16} style={{ color: '#7C5CFC' }} />
                  <span style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
                    Contract Document
                  </span>
                  <span style={{ fontSize: '11px', color: '#475569', marginLeft: 'auto' }}>
                    (Required)
                  </span>
                </div>

                {!uploadedFile ? (
                  <div
                    className="flex flex-col items-center justify-center transition-all duration-200"
                    style={{
                      width: '100%',
                      height: '160px',
                      backgroundColor: dropZoneHover ? 'rgba(124, 92, 252, 0.05)' : '#162033',
                      borderRadius: '14px',
                      border: dropZoneHover
                        ? '1.5px dashed rgba(124, 92, 252, 0.6)'
                        : '1.5px dashed rgba(100, 116, 139, 0.4)',
                      boxShadow: dropZoneHover ? '0 0 24px rgba(124, 92, 252, 0.12)' : 'none',
                      cursor: 'pointer',
                      gap: '8px',
                      padding: '20px'
                    }}
                    onDragEnter={() => setDropZoneHover(true)}
                    onDragLeave={() => setDropZoneHover(false)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      setDropZoneHover(false);
                      handleFileUpload();
                    }}
                    onClick={handleFileUpload}
                  >
                    <div
                      className="flex items-center justify-center rounded-full"
                      style={{
                        width: '44px',
                        height: '44px',
                        backgroundColor: dropZoneHover
                          ? 'rgba(124, 92, 252, 0.18)'
                          : 'rgba(124, 92, 252, 0.10)',
                        border: '1px solid rgba(124, 92, 252, 0.15)'
                      }}
                    >
                      <Scale size={22} style={{ color: '#7C5CFC' }} />
                    </div>
                    <div
                      style={{
                        fontSize: '13px',
                        fontWeight: 600,
                        color: '#F1F5F9',
                        textAlign: 'center'
                      }}
                    >
                      Drag & drop your contract here
                    </div>
                    <div style={{ fontSize: '12px', color: '#475569', textAlign: 'center' }}>
                      or{' '}
                      <span
                        style={{
                          color: '#7C5CFC',
                          textDecoration: 'underline',
                          cursor: 'pointer'
                        }}
                      >
                        browse files
                      </span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#475569', textAlign: 'center' }}>
                      PDF, DOCX, TXT up to 50MB
                    </div>
                  </div>
                ) : (
                  <div
                    className="flex items-center gap-3 px-4"
                    style={{
                      width: '100%',
                      height: '80px',
                      backgroundColor: 'rgba(52, 211, 153, 0.05)',
                      borderRadius: '14px',
                      border: '1.5px solid rgba(52, 211, 153, 0.35)'
                    }}
                  >
                    <div
                      className="flex items-center justify-center rounded-lg"
                      style={{
                        width: '40px',
                        height: '40px',
                        backgroundColor:
                          uploadedFile.type === 'pdf'
                            ? 'rgba(248, 113, 113, 0.12)'
                            : 'rgba(34, 211, 238, 0.12)',
                        flexShrink: 0
                      }}
                    >
                      <FileSearch
                        size={18}
                        style={{
                          color: uploadedFile.type === 'pdf' ? '#F87171' : '#22D3EE'
                        }}
                      />
                    </div>
                    <div className="flex flex-col gap-0.5 flex-1 min-w-0">
                      <div
                        style={{
                          fontSize: '13px',
                          fontWeight: 500,
                          color: '#F1F5F9',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }}
                      >
                        {uploadedFile.name}
                      </div>
                      <div style={{ fontSize: '11px', color: '#475569' }}>
                        {uploadedFile.size} MB · {uploadedFile.type.toUpperCase()} · Ready for
                        analysis
                      </div>
                    </div>
                    <CheckCircle2 size={16} style={{ color: '#34D399', flexShrink: 0 }} />
                    <button
                      className="transition-colors duration-150"
                      style={{ flexShrink: 0 }}
                      onClick={() => setUploadedFile(null)}
                      onMouseEnter={(e) =>
                        ((e.currentTarget.querySelector('svg') as SVGElement).style.color =
                          '#F87171')
                      }
                      onMouseLeave={(e) =>
                        ((e.currentTarget.querySelector('svg') as SVGElement).style.color =
                          '#475569')
                      }
                    >
                      <XCircle size={14} style={{ color: '#475569' }} />
                    </button>
                  </div>
                )}
              </div>

              {/* Analysis Type */}
              <div>
                <div className="mb-2">
                  <SectionLabel>Analysis Type</SectionLabel>
                </div>
                <div className="flex flex-wrap gap-2">
                  {analysisTypes.map((type) => {
                    const isActive =
                      activeAnalysisTypes[type.key as keyof typeof activeAnalysisTypes];
                    return (
                      <button
                        key={type.key}
                        onClick={() =>
                          setActiveAnalysisTypes({
                            ...activeAnalysisTypes,
                            [type.key]: !isActive
                          })
                        }
                        className="transition-all duration-150"
                        style={{
                          height: '30px',
                          padding: '0 12px',
                          borderRadius: '20px',
                          fontSize: '12px',
                          fontWeight: 500,
                          backgroundColor: isActive ? 'rgba(124, 92, 252, 0.12)' : '#162033',
                          border: isActive
                            ? '1px solid rgba(124, 92, 252, 0.4)'
                            : '1px solid #1E2D45',
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
                        {type.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Governing Law */}
              <div>
                <SectionLabel label="Governing Law" />
                <div className="relative">
                  <button
                    className="flex items-center justify-between w-full transition-all duration-150"
                    style={{
                      height: '40px',
                      backgroundColor: '#162033',
                      border: '1px solid #1E2D45',
                      borderRadius: '10px',
                      padding: '0 14px',
                      fontSize: '13px',
                      color: '#F1F5F9'
                    }}
                    onClick={() => setLawDropdownOpen(!lawDropdownOpen)}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'rgba(124, 92, 252, 0.25)';
                    }}
                    onMouseLeave={(e) => {
                      if (!lawDropdownOpen) {
                        e.currentTarget.style.borderColor = '#1E2D45';
                      }
                    }}
                  >
                    <span>{governingLaw}</span>
                    <ChevronDown size={14} style={{ color: '#475569' }} />
                  </button>
                  {lawDropdownOpen && (
                    <div
                      className="absolute top-full left-0 w-full mt-1 overflow-hidden z-10"
                      style={{
                        backgroundColor: '#162033',
                        border: '1px solid #1E2D45',
                        borderRadius: '10px',
                        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)'
                      }}
                    >
                      {lawOptions.map((option) => (
                        <button
                          key={option}
                          className="w-full text-left transition-colors duration-150"
                          style={{
                            height: '36px',
                            padding: '0 14px',
                            fontSize: '13px',
                            color: '#F1F5F9',
                            backgroundColor: 'transparent'
                          }}
                          onClick={() => {
                            setGoverningLaw(option);
                            setLawDropdownOpen(false);
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = '#1C2840';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }}
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Analysis Depth */}
              <div>
                <SectionLabel label="Analysis Depth" />
                <div
                  className="flex gap-1"
                  style={{
                    width: '100%',
                    backgroundColor: '#162033',
                    border: '1px solid #1E2D45',
                    borderRadius: '10px',
                    padding: '4px'
                  }}
                >
                  {depthOptions.map((option) => {
                    const isActive = analysisDepth === option;
                    return (
                      <button
                        key={option}
                        onClick={() => setAnalysisDepth(option)}
                        className="flex items-center justify-center flex-1 transition-all duration-150"
                        style={{
                          height: '32px',
                          borderRadius: '8px',
                          fontSize: '12px',
                          fontWeight: 500,
                          backgroundColor: isActive ? '#0F1829' : 'transparent',
                          color: isActive ? '#F1F5F9' : '#475569',
                          boxShadow: isActive ? '0 1px 4px rgba(0, 0, 0, 0.3)' : 'none'
                        }}
                        onMouseEnter={(e) => {
                          if (!isActive) {
                            e.currentTarget.style.color = '#94A3B8';
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (!isActive) {
                            e.currentTarget.style.color = '#475569';
                          }
                        }}
                      >
                        {option}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Additional Context */}
              <div>
                <SectionLabel label="Additional Context (Optional)" />
                <textarea
                  placeholder="e.g., Focus on liability clauses and termination conditions..."
                  className="w-full bg-transparent outline-none resize-none transition-all duration-150"
                  style={{
                    minHeight: '80px',
                    backgroundColor: '#162033',
                    border: '1px solid #1E2D45',
                    borderRadius: '10px',
                    padding: '12px 14px',
                    fontSize: '12px',
                    color: '#F1F5F9'
                  }}
                  onFocus={(e) => {
                    e.currentTarget.style.borderColor = 'rgba(124, 92, 252, 0.4)';
                    e.currentTarget.style.boxShadow = '0 0 0 3px rgba(124, 92, 252, 0.12)';
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.borderColor = '#1E2D45';
                    e.currentTarget.style.boxShadow = 'none';
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

          {/* Sticky Button Area (56px) */}
          <div
            style={{
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
              <ActionButton
                disabled={!uploadedFile}
                className="w-full flex items-center justify-center gap-2 transition-all duration-200"
                style={{
                  height: '44px',
                  borderRadius: '12px',
                  fontSize: '14px',
                  fontWeight: 600,
                  backgroundColor: uploadedFile ? '#7C5CFC' : '#162033',
                  border: uploadedFile ? 'none' : '1px solid #1E2D45',
                  color: uploadedFile ? 'white' : '#475569',
                  cursor: uploadedFile ? 'pointer' : 'not-allowed'
                }}
                onMouseEnter={(e) => {
                  if (uploadedFile) {
                    e.currentTarget.style.backgroundColor = '#8B6EFD';
                    e.currentTarget.style.boxShadow = '0 4px 20px rgba(124, 92, 252, 0.4)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (uploadedFile) {
                    e.currentTarget.style.backgroundColor = '#7C5CFC';
                    e.currentTarget.style.boxShadow = 'none';
                  }
                }}
                onMouseDown={(e) => {
                  if (uploadedFile) {
                    e.currentTarget.style.backgroundColor = '#6D4FE0';
                  }
                }}
                onMouseUp={(e) => {
                  if (uploadedFile) {
                    e.currentTarget.style.backgroundColor = '#8B6EFD';
                  }
                }}
              >
                <FileSearch size={16} />
                {uploadedFile ? 'Run Contract Analysis' : 'Upload a Contract First'}
              </ActionButton>
            </div>
          </div>
        </div>

        {/* DIVIDER (always at 676px) */}
        <div
          style={{
            width: '100%',
            height: '1px',
            backgroundColor: '#1E2D45',
            flexShrink: 0
          }}
        />

        {/* BOTTOM SECTION - Analysis History (223px fixed) */}
        <div
          className="flex flex-col"
          style={{
            height: '223px',
            flexShrink: 0
          }}
        >
          {/* Sub-header (40px) */}
          <SubHeader
            className="flex items-center justify-between px-4"
            style={{
              height: '40px',
              borderBottom: '1px solid #1E2D45',
              flexShrink: 0
            }}
          >
            <div className="flex items-center gap-1.5">
              <Clock size={14} style={{ color: '#475569' }} />
              <span style={{ fontSize: '12px', fontWeight: 600, color: '#94A3B8' }}>
                Recent Analyses
              </span>
            </div>
            <button
              className="transition-colors duration-150"
              style={{ fontSize: '11px', color: '#475569' }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#94A3B8')}
              onMouseLeave={(e) => (e.currentTarget.style.color = '#475569')}
            >
              View all →
            </button>
          </SubHeader>

          {/* Scrollable history list (183px) */}
          <div
            className="flex-1 overflow-y-auto contract-history-scroll"
            style={{
              height: '183px'
            }}
          >
            <style>
              {`
                .contract-history-scroll::-webkit-scrollbar {
                  width: 4px;
                }
                .contract-history-scroll::-webkit-scrollbar-track {
                  background: transparent;
                }
                .contract-history-scroll::-webkit-scrollbar-thumb {
                  background: rgba(124, 92, 252, 0.25);
                  border-radius: 4px;
                }
                .contract-history-scroll::-webkit-scrollbar-thumb:hover {
                  background: rgba(124, 92, 252, 0.45);
                }
              `}
            </style>
            {historyRows.map((row) => {
              const riskConfig = getRiskConfig(row.risk);
              const RiskIcon = riskConfig.icon;
              const isHovered = hoveredHistoryRow === row.id;

              return (
                <HistoryRow
                  key={row.id}
                  className="w-full flex items-center gap-2.5 px-4 transition-colors duration-150"
                  style={{
                    height: '44px',
                    backgroundColor: isHovered ? '#1C2840' : 'transparent',
                    cursor: 'pointer'
                  }}
                  onMouseEnter={() => setHoveredHistoryRow(row.id)}
                  onMouseLeave={() => setHoveredHistoryRow(null)}
                >
                  {/* Analysis badge */}
                  <div
                    className="flex items-center justify-center"
                    style={{
                      width: '30px',
                      height: '30px',
                      backgroundColor: riskConfig.bg,
                      borderRadius: '8px',
                      flexShrink: 0
                    }}
                  >
                    <RiskIcon size={14} style={{ color: riskConfig.color }} />
                  </div>

                  {/* Center info */}
                  <div className="flex flex-col gap-0.5 flex-1 min-w-0">
                    <div
                      style={{
                        fontSize: '12px',
                        fontWeight: 500,
                        color: '#F1F5F9',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {row.name}
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
                        {row.depth}
                      </div>
                      <div
                        style={{
                          width: '3px',
                          height: '3px',
                          borderRadius: '50%',
                          backgroundColor: '#475569'
                        }}
                      />
                      <div style={{ fontSize: '10px', color: '#475569' }}>{row.time}</div>
                    </div>
                  </div>

                  {/* Right label/chevron */}
                  <div style={{ flexShrink: 0 }}>
                    {isHovered ? (
                      <ChevronRight size={14} style={{ color: '#475569' }} />
                    ) : (
                      <div
                        style={{
                          fontSize: '14px',
                          fontWeight: 600,
                          color: riskConfig.color
                        }}
                      >
                        {riskConfig.label}
                      </div>
                    )}
                  </div>
                </HistoryRow>
              );
            })}
          </div>
        </div>
      </div>

      {/* Column 3 - Main Area (Empty State) */}
      <div
        className="flex-1 flex items-center justify-center relative"
        style={{
          backgroundColor: '#0B1120'
        }}
      >
        {/* Mesh gradients */}
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

        {/* Empty state content */}
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
              <Scale size={32} style={{ color: 'rgba(124, 92, 252, 0.5)' }} />
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
              Upload a contract and run an analysis
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
          <HintChipRow
            chips={[
              { color: '#34D399', label: 'Low risk clauses' },
              { color: '#F59E0B', label: 'Medium risk' },
              { color: '#F87171', label: 'High risk flags' }
            ]}
          />
        </div>
      </div>
    </>
  );
}