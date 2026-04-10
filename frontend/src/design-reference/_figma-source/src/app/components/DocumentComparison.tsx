import { useState } from 'react';
import { Info, CloudUpload, ArrowLeftRight, FileText, CheckCircle2, XCircle, Loader2, Clock, ChevronRight, GitCompare } from 'lucide-react';
import { EmptyState } from './shared';

type ComparisonFocus = 'full' | 'clauses' | 'risk';

interface UploadedFile {
  name: string;
  size: string;
  type: 'pdf' | 'docx' | 'txt';
}

export function DocumentComparison() {
  // Show both files attached by default
  const [doc1, setDoc1] = useState<UploadedFile | null>({ name: 'NDA_Template_2026.pdf', size: '2.4 MB', type: 'pdf' });
  const [doc2, setDoc2] = useState<UploadedFile | null>({ name: 'Contract_Template.docx', size: '1.8 MB', type: 'docx' });
  const [comparisonFocus, setComparisonFocus] = useState<ComparisonFocus>('full');
  const [doc1Hover, setDoc1Hover] = useState(false);
  const [doc2Hover, setDoc2Hover] = useState(false);
  const [hoveredHistoryRow, setHoveredHistoryRow] = useState<number | null>(null);

  const comparisonHistory = [
    { id: 1, name: 'NDA_2026 vs NDA_2025', depth: 'Full', time: '1h ago', status: 'done' },
    { id: 2, name: 'Contract_A vs Contract_B', depth: 'Clauses', time: 'Processing...', status: 'running' },
    { id: 3, name: 'Compliance_Q1 vs Compliance_Q4', depth: 'Risk', time: 'Yesterday', status: 'done' },
    { id: 4, name: 'Service_Agr vs Sales_Agr', depth: 'Full', time: '2d ago', status: 'done' },
    { id: 5, name: 'License_v1 vs License_v2', depth: 'Clauses', time: '3d ago', status: 'failed' },
    { id: 6, name: 'NDA_Draft vs NDA_Final', depth: 'Risk', time: '4d ago', status: 'done' }
  ];

  const getFileTypeConfig = (type: string) => {
    const configs = {
      pdf: { bg: 'rgba(248, 113, 113, 0.12)', color: '#F87171' },
      docx: { bg: 'rgba(34, 211, 238, 0.12)', color: '#22D3EE' },
      txt: { bg: 'rgba(52, 211, 153, 0.12)', color: '#34D399' }
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
      case 'running':
        return <Loader2 size={14} style={{ color: '#F59E0B' }} className="animate-spin" />;
      case 'failed':
        return <XCircle size={14} style={{ color: '#F87171' }} />;
      default:
        return null;
    }
  };

  const handleSwap = () => {
    const temp = doc1;
    setDoc1(doc2);
    setDoc2(temp);
  };

  const isGenerateEnabled = doc1 !== null && doc2 !== null;

  return (
    <>
      {/* Column 2 - Comparison Panel */}
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
                Compare Documents
              </div>
              <div style={{ fontSize: '11px', color: '#475569' }}>
                Upload two documents to compare
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
            <div className="flex flex-col gap-4">
              {/* Document 1 Upload */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <div
                    className="flex items-center justify-center"
                    style={{
                      width: '20px',
                      height: '20px',
                      borderRadius: '50%',
                      backgroundColor: '#7C5CFC',
                      fontSize: '11px',
                      fontWeight: 600,
                      color: 'white'
                    }}
                  >
                    1
                  </div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
                    Document 1
                  </div>
                  <div style={{ fontSize: '11px', color: '#475569', marginLeft: 'auto' }}>
                    (Required)
                  </div>
                </div>

                {doc1 === null ? (
                  <div
                    className="flex flex-col items-center justify-center transition-all duration-200"
                    style={{
                      height: '130px',
                      backgroundColor: doc1Hover ? 'rgba(124, 92, 252, 0.05)' : '#162033',
                      border: doc1Hover 
                        ? '1.5px dashed rgba(124, 92, 252, 0.6)' 
                        : '1.5px dashed rgba(100, 116, 139, 0.4)',
                      borderRadius: '14px',
                      padding: '16px',
                      gap: '6px',
                      cursor: 'pointer'
                    }}
                    onDragEnter={() => setDoc1Hover(true)}
                    onDragLeave={() => setDoc1Hover(false)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      setDoc1Hover(false);
                      setDoc1({ name: 'NDA_Template_2026.pdf', size: '2.4 MB', type: 'pdf' });
                    }}
                    onClick={() => setDoc1({ name: 'NDA_Template_2026.pdf', size: '2.4 MB', type: 'pdf' })}
                  >
                    <div
                      className="flex items-center justify-center"
                      style={{
                        width: '36px',
                        height: '36px',
                        borderRadius: '50%',
                        backgroundColor: doc1Hover ? 'rgba(124, 92, 252, 0.18)' : 'rgba(124, 92, 252, 0.10)'
                      }}
                    >
                      <CloudUpload size={18} style={{ color: '#7C5CFC' }} />
                    </div>
                    <div style={{ fontSize: '12px', color: '#475569', textAlign: 'center' }}>
                      Drag & drop or{' '}
                      <span style={{ color: '#7C5CFC', textDecoration: 'underline' }}>
                        browse
                      </span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#475569', textAlign: 'center' }}>
                      PDF, DOCX, TXT up to 50MB
                    </div>
                  </div>
                ) : (
                  <div
                    className="flex items-center gap-2.5"
                    style={{
                      height: '64px',
                      padding: '14px 16px',
                      backgroundColor: 'rgba(52, 211, 153, 0.05)',
                      border: '1.5px solid rgba(52, 211, 153, 0.35)',
                      borderRadius: '14px'
                    }}
                  >
                    <div
                      className="flex items-center justify-center"
                      style={{
                        width: '36px',
                        height: '36px',
                        borderRadius: '10px',
                        backgroundColor: getFileTypeConfig(doc1.type).bg,
                        flexShrink: 0
                      }}
                    >
                      <FileText size={16} style={{ color: getFileTypeConfig(doc1.type).color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div
                        style={{
                          fontSize: '13px',
                          fontWeight: 500,
                          color: '#F1F5F9',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis'
                        }}
                      >
                        {doc1.name}
                      </div>
                      <div style={{ fontSize: '11px', color: '#475569' }}>
                        {doc1.size} · {doc1.type.toUpperCase()}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 size={16} style={{ color: '#34D399' }} />
                      <button
                        onClick={() => setDoc1(null)}
                        className="transition-opacity duration-150"
                        style={{ opacity: 0.7 }}
                        onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                        onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.7')}
                      >
                        <XCircle size={14} style={{ color: '#475569' }} />
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Swap Button */}
              <div className="flex items-center gap-2" style={{ padding: '4px 0' }}>
                <div style={{ flex: 1, height: '1px', backgroundColor: '#1E2D45' }} />
                <button
                  className="flex items-center gap-1.5 transition-all duration-150"
                  style={{
                    height: '28px',
                    padding: '0 12px',
                    borderRadius: '20px',
                    backgroundColor: '#162033',
                    border: '1px solid #1E2D45'
                  }}
                  onClick={handleSwap}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'rgba(124, 92, 252, 0.4)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = '#1E2D45';
                  }}
                >
                  <ArrowLeftRight size={12} style={{ color: '#475569' }} />
                  <span style={{ fontSize: '11px', color: '#94A3B8' }}>Swap</span>
                </button>
                <div style={{ flex: 1, height: '1px', backgroundColor: '#1E2D45' }} />
              </div>

              {/* Document 2 Upload */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <div
                    className="flex items-center justify-center"
                    style={{
                      width: '20px',
                      height: '20px',
                      borderRadius: '50%',
                      backgroundColor: doc2 ? '#7C5CFC' : '#334155',
                      fontSize: '11px',
                      fontWeight: 600,
                      color: doc2 ? 'white' : '#94A3B8'
                    }}
                  >
                    2
                  </div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
                    Document 2
                  </div>
                  <div style={{ fontSize: '11px', color: '#475569', marginLeft: 'auto' }}>
                    (Required)
                  </div>
                </div>

                {doc2 === null ? (
                  <div
                    className="flex flex-col items-center justify-center transition-all duration-200"
                    style={{
                      height: '130px',
                      backgroundColor: doc2Hover ? 'rgba(124, 92, 252, 0.05)' : '#162033',
                      border: doc2Hover 
                        ? '1.5px dashed rgba(124, 92, 252, 0.6)' 
                        : '1.5px dashed rgba(100, 116, 139, 0.3)',
                      borderRadius: '14px',
                      padding: '16px',
                      gap: '6px',
                      cursor: 'pointer'
                    }}
                    onDragEnter={() => setDoc2Hover(true)}
                    onDragLeave={() => setDoc2Hover(false)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      setDoc2Hover(false);
                      setDoc2({ name: 'Contract_Template.docx', size: '1.8 MB', type: 'docx' });
                    }}
                    onClick={() => setDoc2({ name: 'Contract_Template.docx', size: '1.8 MB', type: 'docx' })}
                  >
                    <div
                      className="flex items-center justify-center"
                      style={{
                        width: '36px',
                        height: '36px',
                        borderRadius: '50%',
                        backgroundColor: doc2Hover ? 'rgba(124, 92, 252, 0.18)' : 'rgba(124, 92, 252, 0.10)'
                      }}
                    >
                      <CloudUpload size={18} style={{ color: '#7C5CFC' }} />
                    </div>
                    <div style={{ fontSize: '12px', color: '#475569', textAlign: 'center' }}>
                      Drag & drop or{' '}
                      <span style={{ color: '#7C5CFC', textDecoration: 'underline' }}>
                        browse
                      </span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#475569', textAlign: 'center' }}>
                      PDF, DOCX, TXT up to 50MB
                    </div>
                  </div>
                ) : (
                  <div
                    className="flex items-center gap-2.5"
                    style={{
                      height: '64px',
                      padding: '14px 16px',
                      backgroundColor: 'rgba(52, 211, 153, 0.05)',
                      border: '1.5px solid rgba(52, 211, 153, 0.35)',
                      borderRadius: '14px'
                    }}
                  >
                    <div
                      className="flex items-center justify-center"
                      style={{
                        width: '36px',
                        height: '36px',
                        borderRadius: '10px',
                        backgroundColor: getFileTypeConfig(doc2.type).bg,
                        flexShrink: 0
                      }}
                    >
                      <FileText size={16} style={{ color: getFileTypeConfig(doc2.type).color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div
                        style={{
                          fontSize: '13px',
                          fontWeight: 500,
                          color: '#F1F5F9',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis'
                        }}
                      >
                        {doc2.name}
                      </div>
                      <div style={{ fontSize: '11px', color: '#475569' }}>
                        {doc2.size} · {doc2.type.toUpperCase()}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 size={16} style={{ color: '#34D399' }} />
                      <button
                        onClick={() => setDoc2(null)}
                        className="transition-opacity duration-150"
                        style={{ opacity: 0.7 }}
                        onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                        onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.7')}
                      >
                        <XCircle size={14} style={{ color: '#475569' }} />
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Comparison Options */}
              <div style={{ marginTop: '4px' }}>
                <div style={{ fontSize: '13px', fontWeight: 500, color: '#F1F5F9', marginBottom: '8px' }}>
                  Comparison Focus (Optional)
                </div>
                <div className="flex flex-wrap gap-2">
                  {[
                    { value: 'full' as ComparisonFocus, label: 'Full Document' },
                    { value: 'clauses' as ComparisonFocus, label: 'Key Clauses Only' },
                    { value: 'risk' as ComparisonFocus, label: 'Risk Differences' }
                  ].map((option) => (
                    <button
                      key={option.value}
                      onClick={() => setComparisonFocus(option.value)}
                      className="transition-all duration-150"
                      style={{
                        height: '30px',
                        padding: '0 12px',
                        borderRadius: '20px',
                        backgroundColor: comparisonFocus === option.value 
                          ? 'rgba(124, 92, 252, 0.12)' 
                          : '#162033',
                        border: comparisonFocus === option.value 
                          ? '1px solid rgba(124, 92, 252, 0.4)' 
                          : '1px solid #1E2D45',
                        fontSize: '12px',
                        fontWeight: 500,
                        color: comparisonFocus === option.value ? '#7C5CFC' : '#94A3B8'
                      }}
                      onMouseEnter={(e) => {
                        if (comparisonFocus !== option.value) {
                          e.currentTarget.style.borderColor = 'rgba(124, 92, 252, 0.4)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (comparisonFocus !== option.value) {
                          e.currentTarget.style.borderColor = '#1E2D45';
                        }
                      }}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Bottom Fade Overlay */}
            <div
              style={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                right: 0,
                height: '40px',
                background: 'linear-gradient(to bottom, transparent, #0F1829)',
                pointerEvents: 'none'
              }}
            />
          </div>

          {/* Sticky Generate Button (56px) */}
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
                disabled={!isGenerateEnabled}
                style={{
                  height: '44px',
                  backgroundColor: isGenerateEnabled ? '#7C5CFC' : '#162033',
                  border: isGenerateEnabled ? 'none' : '1px solid #1E2D45',
                  fontSize: '14px',
                  fontWeight: 600,
                  color: isGenerateEnabled ? 'white' : '#475569',
                  cursor: isGenerateEnabled ? 'pointer' : 'not-allowed'
                }}
                onMouseEnter={(e) => {
                  if (isGenerateEnabled) {
                    e.currentTarget.style.backgroundColor = '#8B6EFD';
                    e.currentTarget.style.boxShadow = '0 4px 20px rgba(124, 92, 252, 0.4)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (isGenerateEnabled) {
                    e.currentTarget.style.backgroundColor = '#7C5CFC';
                    e.currentTarget.style.boxShadow = 'none';
                  }
                }}
              >
                {isGenerateEnabled && <GitCompare size={16} />}
                {isGenerateEnabled ? 'Generate Comparison' : 'Upload Both Documents First'}
              </button>
            </div>
          </div>
        </div>

        {/* DIVIDER (always at 676px) */}
        <div style={{ width: '100%', height: '1px', backgroundColor: '#1E2D45', flexShrink: 0 }} />

        {/* BOTTOM SECTION - Comparison History (223px fixed) */}
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
                Recent Comparisons
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

          {/* Scrollable History List (183px) */}
          <div
            className="flex-1 overflow-y-auto custom-scrollbar relative"
            style={{
              height: '183px'
            }}
          >
            {comparisonHistory.map((item) => {
              const isHovered = hoveredHistoryRow === item.id;
              return (
                <button
                  key={item.id}
                  className="w-full flex items-center gap-2.5 px-4 transition-colors duration-150"
                  style={{
                    height: '44px',
                    backgroundColor: isHovered ? '#1C2840' : 'transparent',
                    cursor: 'pointer',
                    borderLeft: item.status === 'running' ? '3px solid #F59E0B' : '3px solid transparent',
                    paddingLeft: item.status === 'running' ? 'calc(1rem - 3px)' : '1rem'
                  }}
                  onMouseEnter={() => setHoveredHistoryRow(item.id)}
                  onMouseLeave={() => setHoveredHistoryRow(null)}
                >
                  {/* Comparison Badge */}
                  <div
                    className="flex items-center justify-center relative"
                    style={{
                      width: '30px',
                      height: '30px',
                      borderRadius: '8px',
                      backgroundColor: 'rgba(124, 92, 252, 0.12)',
                      flexShrink: 0
                    }}
                  >
                    <FileText size={13} style={{ color: '#7C5CFC', position: 'absolute', left: '6px' }} />
                    <FileText size={13} style={{ color: '#7C5CFC', position: 'absolute', right: '6px' }} />
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
                      {item.name}
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
                        {item.depth}
                      </div>
                      <div
                        style={{
                          width: '3px',
                          height: '3px',
                          borderRadius: '50%',
                          backgroundColor: '#475569'
                        }}
                      />
                      <div style={{ fontSize: '10px', color: '#475569' }}>{item.time}</div>
                    </div>
                  </div>

                  {/* Status Icon */}
                  <div style={{ flexShrink: 0 }}>{getStatusIcon(item.status, isHovered)}</div>
                </button>
              );
            })}
            
            {/* Bottom fade overlay */}
            <div
              className="absolute bottom-0 left-0 right-0 pointer-events-none"
              style={{
                height: '40px',
                background: 'linear-gradient(to top, #0F1829, transparent)'
              }}
            />
          </div>
        </div>
      </div>

      {/* Column 3 - Main Area (Empty State) */}
      <EmptyState
        icon={ArrowLeftRight}
        line1="Upload two documents in the panel on the left"
        line2="then click Generate Comparison to see results"
        hintChips={[
          { color: '#34D399', label: 'Matching clauses' },
          { color: '#F87171', label: 'Differences' },
          { color: '#F59E0B', label: 'Risk flags' }
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

        .animate-spin {
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </>
  );
}