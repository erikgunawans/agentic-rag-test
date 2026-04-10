import { HistorySection } from './shared';
import { FileText, ShieldCheck, GitCompare, FilePlus, Clock, AlertCircle, Search, Zap } from 'lucide-react';

export function HistorySectionReference() {
  // Sample data for each module
  const documentsHistory = [
    { id: 1, title: 'NDA_Template_2026.pdf', subtitle: 'Uploaded & analyzed', time: '2h ago' },
    { id: 2, title: 'PT_Marina_Contract.docx', subtitle: 'Processing complete', time: '5h ago' },
    { id: 3, title: 'Payment_Terms_Draft.docx', subtitle: 'Analysis in progress', time: '1d ago' }
  ];

  const creationHistory = [
    { id: 1, title: 'NDA — Tech Partnership', subtitle: 'Draft saved', time: '30m ago' },
    { id: 2, title: 'Service Agreement Template', subtitle: 'Completed', time: '3h ago' },
    { id: 3, title: 'Employment Contract', subtitle: 'In progress', time: '1d ago' }
  ];

  const comparisonHistory = [
    { id: 1, title: 'Contract v1.2 vs v1.3', subtitle: '14 changes detected', time: '1h ago' },
    { id: 2, title: 'NDA Template Versions', subtitle: '7 differences found', time: '4h ago' },
    { id: 3, title: 'Terms & Conditions Update', subtitle: '22 modifications', time: '2d ago' }
  ];

  const complianceHistory = [
    { id: 1, title: 'OJK Regulation Check', subtitle: 'Passed all criteria', time: '45m ago' },
    { id: 2, title: 'GDPR Compliance Scan', subtitle: '2 issues found', time: '3h ago' },
    { id: 3, title: 'Labor Law Validation', subtitle: 'Compliant', time: '1d ago' }
  ];

  return (
    <div
      className="flex flex-col gap-8 p-8"
      style={{
        backgroundColor: '#0B1120',
        minHeight: '100vh'
      }}
    >
      {/* Title */}
      <div className="flex flex-col items-center gap-3">
        <h1
          style={{
            fontSize: '32px',
            fontWeight: 700,
            color: '#F1F5F9',
            letterSpacing: '-0.02em'
          }}
        >
          History Section{' '}
          <span
            style={{
              background: 'linear-gradient(to right, #7C5CFC, #A78BFA, #60A5FA)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text'
            }}
          >
            Master Component
          </span>
        </h1>
        <p style={{ fontSize: '14px', color: '#94A3B8' }}>
          Reusable 223px history section across all 4 module pages
        </p>
      </div>

      {/* Component Specification */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl mx-auto"
        style={{
          maxWidth: '900px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '16px', fontWeight: 600, color: '#F1F5F9' }}>
          Component Specification
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-3">
            <div className="flex items-start gap-4">
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '100px' }}>
                HEIGHT
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8' }}>223px (fixed)</div>
            </div>

            <div className="flex items-start gap-4">
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '100px' }}>
                HEADER
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8' }}>48px with title & badge</div>
            </div>

            <div className="flex items-start gap-4">
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '100px' }}>
                CONTENT
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8' }}>175px scrollable area</div>
            </div>
          </div>

          <div className="flex flex-col gap-3">
            <div className="flex items-start gap-4">
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '100px' }}>
                BORDER
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8', fontFamily: 'monospace' }}>
                bottom: 1px #1E2D45
              </div>
            </div>

            <div className="flex items-start gap-4">
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '100px' }}>
                STATES
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8' }}>With items / Empty state</div>
            </div>

            <div className="flex items-start gap-4">
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '100px' }}>
                HOVER
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8' }}>Item bg: #1C2840</div>
            </div>
          </div>
        </div>
      </div>

      {/* Badge Icon Variants */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl mx-auto"
        style={{
          maxWidth: '900px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '16px', fontWeight: 600, color: '#F1F5F9' }}>
          Badge Icon Variants
        </div>

        <div className="grid grid-cols-4 gap-3">
          {[
            { variant: 'shield', Icon: ShieldCheck, label: 'Shield' },
            { variant: 'file', Icon: FileText, label: 'File' },
            { variant: 'compare', Icon: GitCompare, label: 'Compare' },
            { variant: 'doc', Icon: FilePlus, label: 'Document' }
          ].map(({ variant, Icon, label }) => (
            <div
              key={variant}
              className="flex flex-col items-center gap-3 p-4 rounded-lg"
              style={{
                backgroundColor: '#162033',
                border: '1px solid #1E2D45'
              }}
            >
              <div
                className="flex items-center justify-center rounded-lg"
                style={{
                  width: '48px',
                  height: '48px',
                  backgroundColor: '#0F1829',
                  border: '1px solid #1E2D45'
                }}
              >
                <Icon size={24} style={{ color: '#94A3B8' }} />
              </div>
              <div style={{ fontSize: '11px', fontWeight: 600, color: '#7C5CFC', fontFamily: 'monospace' }}>
                &quot;{variant}&quot;
              </div>
              <div style={{ fontSize: '11px', color: '#94A3B8' }}>
                {label}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Badge Color Variants */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl mx-auto"
        style={{
          maxWidth: '900px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '16px', fontWeight: 600, color: '#F1F5F9' }}>
          Badge Color Variants
        </div>

        <div className="grid grid-cols-4 gap-3">
          {[
            { color: 'green', bg: 'rgba(52, 211, 153, 0.1)', border: 'rgba(52, 211, 153, 0.3)', text: '#34D399', label: 'Green' },
            { color: 'amber', bg: 'rgba(245, 158, 11, 0.1)', border: 'rgba(245, 158, 11, 0.3)', text: '#F59E0B', label: 'Amber' },
            { color: 'red', bg: 'rgba(248, 113, 113, 0.1)', border: 'rgba(248, 113, 113, 0.3)', text: '#F87171', label: 'Red' },
            { color: 'purple', bg: 'rgba(124, 92, 252, 0.1)', border: 'rgba(124, 92, 252, 0.3)', text: '#7C5CFC', label: 'Purple' }
          ].map(({ color, bg, border, text, label }) => (
            <div
              key={color}
              className="flex flex-col items-center gap-3 p-4 rounded-lg"
              style={{
                backgroundColor: '#162033',
                border: '1px solid #1E2D45'
              }}
            >
              <div
                className="flex items-center gap-1.5 px-3 rounded-md"
                style={{
                  height: '28px',
                  backgroundColor: bg,
                  border: `1px solid ${border}`
                }}
              >
                <ShieldCheck size={14} style={{ color: text }} />
                <span style={{ fontSize: '12px', fontWeight: 600, color: text }}>
                  Active
                </span>
              </div>
              <div style={{ fontSize: '11px', fontWeight: 600, color: text, fontFamily: 'monospace' }}>
                &quot;{color}&quot;
              </div>
              <div style={{ fontSize: '11px', color: '#94A3B8' }}>
                {label}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* All 4 Module Variations */}
      <div className="flex flex-col gap-6">
        <div
          className="flex items-center justify-center gap-2 p-4 rounded-xl mx-auto"
          style={{
            backgroundColor: '#0F1829',
            border: '1px solid #1E2D45'
          }}
        >
          <div
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: '#7C5CFC'
            }}
          />
          <span style={{ fontSize: '14px', fontWeight: 600, color: '#F1F5F9' }}>
            4 Module Variations
          </span>
          <div
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: '#7C5CFC'
            }}
          />
        </div>

        {/* Grid of 4 variations */}
        <div className="grid grid-cols-2 gap-6" style={{ maxWidth: '1200px', margin: '0 auto' }}>
          {/* 1. Documents Module */}
          <div
            className="flex flex-col rounded-2xl overflow-hidden"
            style={{
              backgroundColor: '#0F1829',
              border: '1px solid #1E2D45'
            }}
          >
            <div className="flex items-center gap-2 p-4" style={{ borderBottom: '1px solid #1E2D45' }}>
              <div
                style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(52, 211, 153, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '12px',
                  fontWeight: 700,
                  color: '#34D399'
                }}
              >
                1
              </div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
                Documents Module
              </div>
            </div>

            <div style={{ backgroundColor: '#0F1829' }}>
              <HistorySection
                sectionTitle="RECENT UPLOADS"
                badgeIcon="file"
                badgeColor="green"
                statusLabel="3 Active"
                emptyStateIcon={FileText}
                items={documentsHistory}
              />
            </div>

            <div className="p-4" style={{ backgroundColor: '#162033' }}>
              <div
                className="p-3 rounded-lg"
                style={{
                  backgroundColor: '#0F1829',
                  border: '1px solid #1E2D45',
                  fontFamily: 'monospace',
                  fontSize: '10px',
                  color: '#94A3B8'
                }}
              >
                <div style={{ color: '#34D399' }}>&lt;HistorySection</div>
                <div style={{ marginLeft: '8px' }}>sectionTitle=&quot;RECENT UPLOADS&quot;</div>
                <div style={{ marginLeft: '8px' }}>badgeIcon=&quot;file&quot;</div>
                <div style={{ marginLeft: '8px' }}>badgeColor=&quot;green&quot;</div>
                <div style={{ marginLeft: '8px' }}>statusLabel=&quot;3 Active&quot;</div>
                <div style={{ marginLeft: '8px' }}>items={'{documentsHistory}'}</div>
                <div style={{ color: '#34D399' }}>{'/>'}</div>
              </div>
            </div>
          </div>

          {/* 2. Create Document Module */}
          <div
            className="flex flex-col rounded-2xl overflow-hidden"
            style={{
              backgroundColor: '#0F1829',
              border: '1px solid #1E2D45'
            }}
          >
            <div className="flex items-center gap-2 p-4" style={{ borderBottom: '1px solid #1E2D45' }}>
              <div
                style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(124, 92, 252, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '12px',
                  fontWeight: 700,
                  color: '#7C5CFC'
                }}
              >
                2
              </div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
                Create Document Module
              </div>
            </div>

            <div style={{ backgroundColor: '#0F1829' }}>
              <HistorySection
                sectionTitle="RECENT DRAFTS"
                badgeIcon="doc"
                badgeColor="purple"
                statusLabel="3 Drafts"
                emptyStateIcon={FilePlus}
                items={creationHistory}
              />
            </div>

            <div className="p-4" style={{ backgroundColor: '#162033' }}>
              <div
                className="p-3 rounded-lg"
                style={{
                  backgroundColor: '#0F1829',
                  border: '1px solid #1E2D45',
                  fontFamily: 'monospace',
                  fontSize: '10px',
                  color: '#94A3B8'
                }}
              >
                <div style={{ color: '#7C5CFC' }}>&lt;HistorySection</div>
                <div style={{ marginLeft: '8px' }}>sectionTitle=&quot;RECENT DRAFTS&quot;</div>
                <div style={{ marginLeft: '8px' }}>badgeIcon=&quot;doc&quot;</div>
                <div style={{ marginLeft: '8px' }}>badgeColor=&quot;purple&quot;</div>
                <div style={{ marginLeft: '8px' }}>statusLabel=&quot;3 Drafts&quot;</div>
                <div style={{ marginLeft: '8px' }}>items={'{creationHistory}'}</div>
                <div style={{ color: '#7C5CFC' }}>{'/>'}</div>
              </div>
            </div>
          </div>

          {/* 3. Compare Documents Module */}
          <div
            className="flex flex-col rounded-2xl overflow-hidden"
            style={{
              backgroundColor: '#0F1829',
              border: '1px solid #1E2D45'
            }}
          >
            <div className="flex items-center gap-2 p-4" style={{ borderBottom: '1px solid #1E2D45' }}>
              <div
                style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(34, 211, 238, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '12px',
                  fontWeight: 700,
                  color: '#22D3EE'
                }}
              >
                3
              </div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
                Compare Documents Module
              </div>
            </div>

            <div style={{ backgroundColor: '#0F1829' }}>
              <HistorySection
                sectionTitle="COMPARISON HISTORY"
                badgeIcon="compare"
                badgeColor="amber"
                statusLabel="3 Recent"
                emptyStateIcon={GitCompare}
                items={comparisonHistory}
              />
            </div>

            <div className="p-4" style={{ backgroundColor: '#162033' }}>
              <div
                className="p-3 rounded-lg"
                style={{
                  backgroundColor: '#0F1829',
                  border: '1px solid #1E2D45',
                  fontFamily: 'monospace',
                  fontSize: '10px',
                  color: '#94A3B8'
                }}
              >
                <div style={{ color: '#22D3EE' }}>&lt;HistorySection</div>
                <div style={{ marginLeft: '8px' }}>sectionTitle=&quot;COMPARISON HISTORY&quot;</div>
                <div style={{ marginLeft: '8px' }}>badgeIcon=&quot;compare&quot;</div>
                <div style={{ marginLeft: '8px' }}>badgeColor=&quot;amber&quot;</div>
                <div style={{ marginLeft: '8px' }}>statusLabel=&quot;3 Recent&quot;</div>
                <div style={{ marginLeft: '8px' }}>items={'{comparisonHistory}'}</div>
                <div style={{ color: '#22D3EE' }}>{'/>'}</div>
              </div>
            </div>
          </div>

          {/* 4. Compliance Check Module */}
          <div
            className="flex flex-col rounded-2xl overflow-hidden"
            style={{
              backgroundColor: '#0F1829',
              border: '1px solid #1E2D45'
            }}
          >
            <div className="flex items-center gap-2 p-4" style={{ borderBottom: '1px solid #1E2D45' }}>
              <div
                style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(248, 113, 113, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '12px',
                  fontWeight: 700,
                  color: '#F87171'
                }}
              >
                4
              </div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
                Compliance Check Module
              </div>
            </div>

            <div style={{ backgroundColor: '#0F1829' }}>
              <HistorySection
                sectionTitle="CHECK HISTORY"
                badgeIcon="shield"
                badgeColor="red"
                statusLabel="3 Checked"
                emptyStateIcon={ShieldCheck}
                items={complianceHistory}
              />
            </div>

            <div className="p-4" style={{ backgroundColor: '#162033' }}>
              <div
                className="p-3 rounded-lg"
                style={{
                  backgroundColor: '#0F1829',
                  border: '1px solid #1E2D45',
                  fontFamily: 'monospace',
                  fontSize: '10px',
                  color: '#94A3B8'
                }}
              >
                <div style={{ color: '#F87171' }}>&lt;HistorySection</div>
                <div style={{ marginLeft: '8px' }}>sectionTitle=&quot;CHECK HISTORY&quot;</div>
                <div style={{ marginLeft: '8px' }}>badgeIcon=&quot;shield&quot;</div>
                <div style={{ marginLeft: '8px' }}>badgeColor=&quot;red&quot;</div>
                <div style={{ marginLeft: '8px' }}>statusLabel=&quot;3 Checked&quot;</div>
                <div style={{ marginLeft: '8px' }}>items={'{complianceHistory}'}</div>
                <div style={{ color: '#F87171' }}>{'/>'}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Empty State Variations */}
      <div className="flex flex-col gap-6">
        <div
          className="flex items-center justify-center gap-2 p-4 rounded-xl mx-auto"
          style={{
            backgroundColor: '#0F1829',
            border: '1px solid #1E2D45'
          }}
        >
          <span style={{ fontSize: '14px', fontWeight: 600, color: '#F1F5F9' }}>
            Empty State Variations
          </span>
        </div>

        <div className="grid grid-cols-4 gap-4" style={{ maxWidth: '1200px', margin: '0 auto' }}>
          {[
            { icon: FileText, label: 'No uploads', color: '#34D399' },
            { icon: FilePlus, label: 'No drafts', color: '#7C5CFC' },
            { icon: GitCompare, label: 'No comparisons', color: '#F59E0B' },
            { icon: ShieldCheck, label: 'No checks', color: '#F87171' }
          ].map(({ icon: Icon, label, color }, index) => (
            <div
              key={index}
              className="flex flex-col rounded-2xl overflow-hidden"
              style={{
                backgroundColor: '#0F1829',
                border: '1px solid #1E2D45'
              }}
            >
              <div style={{ backgroundColor: '#0F1829' }}>
                <HistorySection
                  sectionTitle="EMPTY STATE"
                  badgeIcon={['file', 'doc', 'compare', 'shield'][index] as any}
                  badgeColor={['green', 'purple', 'amber', 'red'][index] as any}
                  statusLabel="0 Items"
                  emptyStateIcon={Icon}
                  items={[]}
                />
              </div>
              <div className="p-3 text-center" style={{ backgroundColor: '#162033', borderTop: '1px solid #1E2D45' }}>
                <div style={{ fontSize: '11px', color: '#64748B' }}>
                  {label}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Component Properties */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl mx-auto"
        style={{
          maxWidth: '900px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '16px', fontWeight: 600, color: '#F1F5F9' }}>
          Component Properties
        </div>

        <div className="flex flex-col gap-3">
          <div
            className="flex items-start gap-4 p-3 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#7C5CFC', minWidth: '150px' }}>
              sectionTitle
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', color: '#F1F5F9' }}>
                string (required)
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                Header title text (e.g., "RECENT UPLOADS", "CHECK HISTORY")
              </div>
            </div>
          </div>

          <div
            className="flex items-start gap-4 p-3 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#7C5CFC', minWidth: '150px' }}>
              badgeIcon
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', color: '#F1F5F9' }}>
                BadgeIconVariant (required)
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                Icon type: 'shield' | 'file' | 'compare' | 'doc'
              </div>
            </div>
          </div>

          <div
            className="flex items-start gap-4 p-3 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#7C5CFC', minWidth: '150px' }}>
              badgeColor
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', color: '#F1F5F9' }}>
                BadgeColor (required)
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                Color scheme: 'green' | 'amber' | 'red' | 'purple'
              </div>
            </div>
          </div>

          <div
            className="flex items-start gap-4 p-3 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#7C5CFC', minWidth: '150px' }}>
              statusLabel
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', color: '#F1F5F9' }}>
                string (required)
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                Badge text (e.g., "3 Active", "0 Items")
              </div>
            </div>
          </div>

          <div
            className="flex items-start gap-4 p-3 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#7C5CFC', minWidth: '150px' }}>
              emptyStateIcon
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', color: '#F1F5F9' }}>
                LucideIcon (optional)
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                Icon shown when no items exist. Default: Clock
              </div>
            </div>
          </div>

          <div
            className="flex items-start gap-4 p-3 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#7C5CFC', minWidth: '150px' }}>
              items
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', color: '#F1F5F9' }}>
                HistoryItem[] (optional)
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                Array of history items. Default: [] (empty state)
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* HistoryItem Interface */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl mx-auto"
        style={{
          maxWidth: '900px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '16px', fontWeight: 600, color: '#F1F5F9' }}>
          HistoryItem Interface
        </div>

        <div
          className="p-4 rounded-lg"
          style={{
            backgroundColor: '#162033',
            border: '1px solid #1E2D45',
            fontFamily: 'monospace',
            fontSize: '12px',
            color: '#94A3B8'
          }}
        >
          <pre style={{ margin: 0 }}>
{`interface HistoryItem {
  id: number;
  title: string;
  subtitle: string;
  time: string;
}`}
          </pre>
        </div>
      </div>
    </div>
  );
}