import { ComplianceStatusBadge } from './shared/ComplianceStatusBadge';

export function ComplianceStatusReference() {
  return (
    <div
      className="flex gap-8 p-8 overflow-x-auto"
      style={{
        backgroundColor: '#0B1120',
        minHeight: '100vh'
      }}
    >
      {/* Pass State */}
      <div
        className="flex flex-col gap-6 p-6 rounded-2xl"
        style={{
          width: '360px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45',
          flexShrink: 0
        }}
      >
        <div>
          <div style={{ fontSize: '18px', fontWeight: 600, color: '#F1F5F9', marginBottom: '4px' }}>
            Pass Status
          </div>
          <div style={{ fontSize: '13px', color: '#94A3B8' }}>
            Document meets all compliance requirements
          </div>
        </div>

        {/* Large Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: LARGE
          </div>
          <ComplianceStatusBadge status="pass" size="lg" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            32px height • 16px icon • 13px text
          </div>
        </div>

        {/* Medium Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: MEDIUM (DEFAULT)
          </div>
          <ComplianceStatusBadge status="pass" size="md" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            28px height • 14px icon • 12px text
          </div>
        </div>

        {/* Small Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: SMALL
          </div>
          <ComplianceStatusBadge status="pass" size="sm" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            24px height • 12px icon • 11px text
          </div>
        </div>

        {/* Technical Specs */}
        <div className="flex flex-col gap-2 pt-4" style={{ borderTop: '1px solid #1E2D45' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            TECHNICAL SPECS
          </div>
          <div className="flex flex-col gap-1" style={{ fontSize: '11px', color: '#64748B' }}>
            <div>Icon: shield-check</div>
            <div>Color: #34D399</div>
            <div>Background: rgba(52,211,153,0.12)</div>
            <div>Label: 'Passed'</div>
            <div>Border Radius: 6px</div>
          </div>
        </div>

        {/* Visual Sample */}
        <div
          className="flex items-center justify-center"
          style={{
            height: '80px',
            backgroundColor: '#162033',
            borderRadius: '12px',
            border: '1px solid #1E2D45'
          }}
        >
          <ComplianceStatusBadge status="pass" size="lg" />
        </div>
      </div>

      {/* Review State */}
      <div
        className="flex flex-col gap-6 p-6 rounded-2xl"
        style={{
          width: '360px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45',
          flexShrink: 0
        }}
      >
        <div>
          <div style={{ fontSize: '18px', fontWeight: 600, color: '#F1F5F9', marginBottom: '4px' }}>
            Review Status
          </div>
          <div style={{ fontSize: '13px', color: '#94A3B8' }}>
            Document requires manual review
          </div>
        </div>

        {/* Large Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: LARGE
          </div>
          <ComplianceStatusBadge status="review" size="lg" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            32px height • 16px icon • 13px text
          </div>
        </div>

        {/* Medium Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: MEDIUM (DEFAULT)
          </div>
          <ComplianceStatusBadge status="review" size="md" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            28px height • 14px icon • 12px text
          </div>
        </div>

        {/* Small Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: SMALL
          </div>
          <ComplianceStatusBadge status="review" size="sm" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            24px height • 12px icon • 11px text
          </div>
        </div>

        {/* Technical Specs */}
        <div className="flex flex-col gap-2 pt-4" style={{ borderTop: '1px solid #1E2D45' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            TECHNICAL SPECS
          </div>
          <div className="flex flex-col gap-1" style={{ fontSize: '11px', color: '#64748B' }}>
            <div>Icon: shield-alert</div>
            <div>Color: #F59E0B</div>
            <div>Background: rgba(245,158,11,0.12)</div>
            <div>Label: 'Review'</div>
            <div>Border Radius: 6px</div>
          </div>
        </div>

        {/* Visual Sample */}
        <div
          className="flex items-center justify-center"
          style={{
            height: '80px',
            backgroundColor: '#162033',
            borderRadius: '12px',
            border: '1px solid #1E2D45'
          }}
        >
          <ComplianceStatusBadge status="review" size="lg" />
        </div>
      </div>

      {/* Fail State */}
      <div
        className="flex flex-col gap-6 p-6 rounded-2xl"
        style={{
          width: '360px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45',
          flexShrink: 0
        }}
      >
        <div>
          <div style={{ fontSize: '18px', fontWeight: 600, color: '#F1F5F9', marginBottom: '4px' }}>
            Fail Status
          </div>
          <div style={{ fontSize: '13px', color: '#94A3B8' }}>
            Document does not meet compliance
          </div>
        </div>

        {/* Large Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: LARGE
          </div>
          <ComplianceStatusBadge status="fail" size="lg" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            32px height • 16px icon • 13px text
          </div>
        </div>

        {/* Medium Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: MEDIUM (DEFAULT)
          </div>
          <ComplianceStatusBadge status="fail" size="md" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            28px height • 14px icon • 12px text
          </div>
        </div>

        {/* Small Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: SMALL
          </div>
          <ComplianceStatusBadge status="fail" size="sm" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            24px height • 12px icon • 11px text
          </div>
        </div>

        {/* Technical Specs */}
        <div className="flex flex-col gap-2 pt-4" style={{ borderTop: '1px solid #1E2D45' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            TECHNICAL SPECS
          </div>
          <div className="flex flex-col gap-1" style={{ fontSize: '11px', color: '#64748B' }}>
            <div>Icon: shield-x</div>
            <div>Color: #F87171</div>
            <div>Background: rgba(248,113,113,0.12)</div>
            <div>Label: 'Failed'</div>
            <div>Border Radius: 6px</div>
          </div>
        </div>

        {/* Visual Sample */}
        <div
          className="flex items-center justify-center"
          style={{
            height: '80px',
            backgroundColor: '#162033',
            borderRadius: '12px',
            border: '1px solid #1E2D45'
          }}
        >
          <ComplianceStatusBadge status="fail" size="lg" />
        </div>
      </div>

      {/* Combined Usage Example */}
      <div
        className="flex flex-col gap-6 p-6 rounded-2xl"
        style={{
          width: '400px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45',
          flexShrink: 0
        }}
      >
        <div>
          <div style={{ fontSize: '18px', fontWeight: 600, color: '#F1F5F9', marginBottom: '4px' }}>
            Usage Examples
          </div>
          <div style={{ fontSize: '13px', color: '#94A3B8' }}>
            Real-world badge implementations
          </div>
        </div>

        {/* In Document List */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            IN DOCUMENT LIST
          </div>
          
          {/* Document Row 1 */}
          <div
            className="flex items-center justify-between p-3 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div className="flex flex-col gap-1">
              <div style={{ fontSize: '13px', fontWeight: 500, color: '#F1F5F9' }}>
                Contract_2026.pdf
              </div>
              <div style={{ fontSize: '11px', color: '#475569' }}>
                Legal • 2.4 MB
              </div>
            </div>
            <ComplianceStatusBadge status="pass" size="sm" />
          </div>

          {/* Document Row 2 */}
          <div
            className="flex items-center justify-between p-3 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div className="flex flex-col gap-1">
              <div style={{ fontSize: '13px', fontWeight: 500, color: '#F1F5F9' }}>
                NDA_Template.docx
              </div>
              <div style={{ fontSize: '11px', color: '#475569' }}>
                Agreement • 1.8 MB
              </div>
            </div>
            <ComplianceStatusBadge status="review" size="sm" />
          </div>

          {/* Document Row 3 */}
          <div
            className="flex items-center justify-between p-3 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div className="flex flex-col gap-1">
              <div style={{ fontSize: '13px', fontWeight: 500, color: '#F1F5F9' }}>
                Service_Agreement.pdf
              </div>
              <div style={{ fontSize: '11px', color: '#475569' }}>
                Contract • 3.1 MB
              </div>
            </div>
            <ComplianceStatusBadge status="fail" size="sm" />
          </div>
        </div>

        {/* In History Row */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            IN COMPLIANCE HISTORY
          </div>

          {/* History Row 1 */}
          <div
            className="flex items-center gap-3 p-3 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', fontWeight: 500, color: '#F1F5F9' }}>
                Q1 Compliance Check
              </div>
              <div style={{ fontSize: '10px', color: '#475569' }}>
                2 hours ago
              </div>
            </div>
            <ComplianceStatusBadge status="pass" size="md" />
          </div>

          {/* History Row 2 */}
          <div
            className="flex items-center gap-3 p-3 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', fontWeight: 500, color: '#F1F5F9' }}>
                Contract Audit - March
              </div>
              <div style={{ fontSize: '10px', color: '#475569' }}>
                Yesterday
              </div>
            </div>
            <ComplianceStatusBadge status="review" size="md" />
          </div>

          {/* History Row 3 */}
          <div
            className="flex items-center gap-3 p-3 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', fontWeight: 500, color: '#F1F5F9' }}>
                Annual Review 2025
              </div>
              <div style={{ fontSize: '10px', color: '#475569' }}>
                3 days ago
              </div>
            </div>
            <ComplianceStatusBadge status="fail" size="md" />
          </div>
        </div>

        {/* Size Comparison */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            ALL SIZES SIDE-BY-SIDE
          </div>

          <div className="flex items-center gap-3">
            <ComplianceStatusBadge status="pass" size="sm" />
            <ComplianceStatusBadge status="pass" size="md" />
            <ComplianceStatusBadge status="pass" size="lg" />
          </div>

          <div className="flex items-center gap-3">
            <ComplianceStatusBadge status="review" size="sm" />
            <ComplianceStatusBadge status="review" size="md" />
            <ComplianceStatusBadge status="review" size="lg" />
          </div>

          <div className="flex items-center gap-3">
            <ComplianceStatusBadge status="fail" size="sm" />
            <ComplianceStatusBadge status="fail" size="md" />
            <ComplianceStatusBadge status="fail" size="lg" />
          </div>
        </div>
      </div>
    </div>
  );
}
