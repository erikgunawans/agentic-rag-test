import { useState } from 'react';
import { AnalysisDepthControl, AnalysisDepth, RiskBadge } from './shared';

export function AnalysisControlsReference() {
  const [quickDepth, setQuickDepth] = useState<AnalysisDepth>('quick');
  const [standardDepth, setStandardDepth] = useState<AnalysisDepth>('standard');
  const [deepDepth, setDeepDepth] = useState<AnalysisDepth>('deep');
  const [interactiveDepth, setInteractiveDepth] = useState<AnalysisDepth>('standard');

  return (
    <div
      className="flex gap-8 p-8 overflow-x-auto"
      style={{
        backgroundColor: '#0B1120',
        minHeight: '100vh'
      }}
    >
      {/* Analysis Depth Control - Quick State */}
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
            Analysis Depth Control
          </div>
          <div style={{ fontSize: '13px', color: '#94A3B8' }}>
            Segmented control with Quick active
          </div>
        </div>

        {/* Large Size - Quick Active */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            LARGE SIZE - QUICK ACTIVE
          </div>
          <AnalysisDepthControl value={quickDepth} onChange={setQuickDepth} size="lg" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            48px height • 14px text • 96px segment width
          </div>
        </div>

        {/* Medium Size - Quick Active */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            MEDIUM SIZE - QUICK ACTIVE (DEFAULT)
          </div>
          <AnalysisDepthControl value={quickDepth} onChange={setQuickDepth} size="md" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            40px height • 13px text • 80px segment width
          </div>
        </div>

        {/* Small Size - Quick Active */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SMALL SIZE - QUICK ACTIVE
          </div>
          <AnalysisDepthControl value={quickDepth} onChange={setQuickDepth} size="sm" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            32px height • 11px text • 64px segment width
          </div>
        </div>

        {/* Technical Specs */}
        <div className="flex flex-col gap-3 pt-4" style={{ borderTop: '1px solid #1E2D45' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            ACTIVE SEGMENT SPECS
          </div>
          <div className="flex flex-col gap-1" style={{ fontSize: '11px', color: '#64748B' }}>
            <div>Background: #0F1829</div>
            <div>Shadow: 0 1px 4px rgba(0,0,0,0.3)</div>
            <div>Text Color: #F1F5F9</div>
            <div>Font Weight: 600</div>
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            INACTIVE SEGMENT SPECS
          </div>
          <div className="flex flex-col gap-1" style={{ fontSize: '11px', color: '#64748B' }}>
            <div>Background: transparent</div>
            <div>Text Color: #475569</div>
            <div>Font Weight: 600</div>
          </div>
        </div>
      </div>

      {/* Analysis Depth Control - Standard State */}
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
            Analysis Depth Control
          </div>
          <div style={{ fontSize: '13px', color: '#94A3B8' }}>
            Segmented control with Standard active
          </div>
        </div>

        {/* Large Size - Standard Active */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            LARGE SIZE - STANDARD ACTIVE
          </div>
          <AnalysisDepthControl value={standardDepth} onChange={setStandardDepth} size="lg" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            48px height • 14px text • 96px segment width
          </div>
        </div>

        {/* Medium Size - Standard Active */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            MEDIUM SIZE - STANDARD ACTIVE (DEFAULT)
          </div>
          <AnalysisDepthControl value={standardDepth} onChange={setStandardDepth} size="md" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            40px height • 13px text • 80px segment width
          </div>
        </div>

        {/* Small Size - Standard Active */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SMALL SIZE - STANDARD ACTIVE
          </div>
          <AnalysisDepthControl value={standardDepth} onChange={setStandardDepth} size="sm" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            32px height • 11px text • 64px segment width
          </div>
        </div>

        {/* Container Specs */}
        <div className="flex flex-col gap-3 pt-4" style={{ borderTop: '1px solid #1E2D45' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            CONTAINER SPECS
          </div>
          <div className="flex flex-col gap-1" style={{ fontSize: '11px', color: '#64748B' }}>
            <div>Background: #162033</div>
            <div>Border: 1px solid #1E2D45</div>
            <div>Border Radius: 12px</div>
            <div>Padding: 4px (md), 3px (sm), 5px (lg)</div>
          </div>
        </div>

        {/* Visual Sample */}
        <div
          className="flex items-center justify-center"
          style={{
            height: '100px',
            backgroundColor: '#162033',
            borderRadius: '12px',
            border: '1px solid #1E2D45'
          }}
        >
          <AnalysisDepthControl value={standardDepth} onChange={setStandardDepth} size="lg" />
        </div>
      </div>

      {/* Analysis Depth Control - Deep State */}
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
            Analysis Depth Control
          </div>
          <div style={{ fontSize: '13px', color: '#94A3B8' }}>
            Segmented control with Deep active
          </div>
        </div>

        {/* Large Size - Deep Active */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            LARGE SIZE - DEEP ACTIVE
          </div>
          <AnalysisDepthControl value={deepDepth} onChange={setDeepDepth} size="lg" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            48px height • 14px text • 96px segment width
          </div>
        </div>

        {/* Medium Size - Deep Active */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            MEDIUM SIZE - DEEP ACTIVE (DEFAULT)
          </div>
          <AnalysisDepthControl value={deepDepth} onChange={setDeepDepth} size="md" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            40px height • 13px text • 80px segment width
          </div>
        </div>

        {/* Small Size - Deep Active */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SMALL SIZE - DEEP ACTIVE
          </div>
          <AnalysisDepthControl value={deepDepth} onChange={setDeepDepth} size="sm" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            32px height • 11px text • 64px segment width
          </div>
        </div>

        {/* Interactive Example */}
        <div className="flex flex-col gap-3 pt-4" style={{ borderTop: '1px solid #1E2D45' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            INTERACTIVE EXAMPLE
          </div>
          <div style={{ fontSize: '12px', color: '#94A3B8', marginBottom: '8px' }}>
            Click segments to change active state
          </div>
          <AnalysisDepthControl 
            value={interactiveDepth} 
            onChange={setInteractiveDepth} 
            size="lg" 
          />
          <div 
            className="flex items-center justify-center rounded-lg"
            style={{
              height: '48px',
              backgroundColor: '#162033',
              border: '1px solid #1E2D45',
              fontSize: '13px',
              fontWeight: 600,
              color: '#7C5CFC'
            }}
          >
            Current: {interactiveDepth.charAt(0).toUpperCase() + interactiveDepth.slice(1)}
          </div>
        </div>
      </div>

      {/* Risk Badges - Low Risk */}
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
            Risk Badge - Low
          </div>
          <div style={{ fontSize: '13px', color: '#94A3B8' }}>
            Document has low risk level
          </div>
        </div>

        {/* Large Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: LARGE
          </div>
          <RiskBadge risk="low" size="lg" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            32px height • 16px icon • 13px text
          </div>
        </div>

        {/* Medium Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: MEDIUM (DEFAULT)
          </div>
          <RiskBadge risk="low" size="md" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            28px height • 14px icon • 12px text
          </div>
        </div>

        {/* Small Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: SMALL
          </div>
          <RiskBadge risk="low" size="sm" />
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
            <div>Icon: file-check</div>
            <div>Color: #34D399</div>
            <div>Background: rgba(52,211,153,0.12)</div>
            <div>Label: 'Low Risk'</div>
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
          <RiskBadge risk="low" size="lg" />
        </div>
      </div>

      {/* Risk Badges - Medium Risk */}
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
            Risk Badge - Medium
          </div>
          <div style={{ fontSize: '13px', color: '#94A3B8' }}>
            Document has medium risk level
          </div>
        </div>

        {/* Large Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: LARGE
          </div>
          <RiskBadge risk="medium" size="lg" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            32px height • 16px icon • 13px text
          </div>
        </div>

        {/* Medium Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: MEDIUM (DEFAULT)
          </div>
          <RiskBadge risk="medium" size="md" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            28px height • 14px icon • 12px text
          </div>
        </div>

        {/* Small Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: SMALL
          </div>
          <RiskBadge risk="medium" size="sm" />
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
            <div>Icon: file-warning</div>
            <div>Color: #F59E0B</div>
            <div>Background: rgba(245,158,11,0.12)</div>
            <div>Label: 'Med Risk'</div>
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
          <RiskBadge risk="medium" size="lg" />
        </div>
      </div>

      {/* Risk Badges - High Risk */}
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
            Risk Badge - High
          </div>
          <div style={{ fontSize: '13px', color: '#94A3B8' }}>
            Document has high risk level
          </div>
        </div>

        {/* Large Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: LARGE
          </div>
          <RiskBadge risk="high" size="lg" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            32px height • 16px icon • 13px text
          </div>
        </div>

        {/* Medium Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: MEDIUM (DEFAULT)
          </div>
          <RiskBadge risk="high" size="md" />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            28px height • 14px icon • 12px text
          </div>
        </div>

        {/* Small Size */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            SIZE: SMALL
          </div>
          <RiskBadge risk="high" size="sm" />
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
            <div>Icon: file-x</div>
            <div>Color: #F87171</div>
            <div>Background: rgba(248,113,113,0.12)</div>
            <div>Label: 'High Risk'</div>
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
          <RiskBadge risk="high" size="lg" />
        </div>
      </div>

      {/* Combined Usage Examples */}
      <div
        className="flex flex-col gap-6 p-6 rounded-2xl"
        style={{
          width: '460px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45',
          flexShrink: 0
        }}
      >
        <div>
          <div style={{ fontSize: '18px', fontWeight: 600, color: '#F1F5F9', marginBottom: '4px' }}>
            Combined Usage
          </div>
          <div style={{ fontSize: '13px', color: '#94A3B8' }}>
            Real-world component implementations
          </div>
        </div>

        {/* Analysis Form Example */}
        <div className="flex flex-col gap-4">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            IN ANALYSIS FORM
          </div>
          
          <div
            className="flex flex-col gap-4 p-4 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div className="flex flex-col gap-2">
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#F1F5F9' }}>
                Analysis Depth
              </div>
              <AnalysisDepthControl 
                value={interactiveDepth} 
                onChange={setInteractiveDepth} 
                size="md" 
              />
            </div>

            <div className="flex items-center justify-between">
              <div style={{ fontSize: '12px', color: '#94A3B8' }}>
                Estimated Time:
              </div>
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#F1F5F9' }}>
                {interactiveDepth === 'quick' ? '2-5 min' : 
                 interactiveDepth === 'standard' ? '10-15 min' : '30-45 min'}
              </div>
            </div>
          </div>
        </div>

        {/* Document List with Risk Badges */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            IN DOCUMENT LIST
          </div>

          {/* Document 1 */}
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
                Legal • 3.2 MB
              </div>
            </div>
            <RiskBadge risk="low" size="sm" />
          </div>

          {/* Document 2 */}
          <div
            className="flex items-center justify-between p-3 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div className="flex flex-col gap-1">
              <div style={{ fontSize: '13px', fontWeight: 500, color: '#F1F5F9' }}>
                Partnership_Contract.docx
              </div>
              <div style={{ fontSize: '11px', color: '#475569' }}>
                Contract • 1.9 MB
              </div>
            </div>
            <RiskBadge risk="medium" size="sm" />
          </div>

          {/* Document 3 */}
          <div
            className="flex items-center justify-between p-3 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div className="flex flex-col gap-1">
              <div style={{ fontSize: '13px', fontWeight: 500, color: '#F1F5F9' }}>
                Liability_Waiver.pdf
              </div>
              <div style={{ fontSize: '11px', color: '#475569' }}>
                Legal • 2.7 MB
              </div>
            </div>
            <RiskBadge risk="high" size="sm" />
          </div>
        </div>

        {/* All Sizes Side-by-Side */}
        <div className="flex flex-col gap-4 pt-4" style={{ borderTop: '1px solid #1E2D45' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            ALL RISK LEVELS
          </div>

          <div className="flex items-center gap-3">
            <RiskBadge risk="low" size="md" />
            <RiskBadge risk="medium" size="md" />
            <RiskBadge risk="high" size="md" />
          </div>

          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            ALL ANALYSIS STATES
          </div>

          <div className="flex flex-col gap-3">
            <AnalysisDepthControl value="quick" size="md" />
            <AnalysisDepthControl value="standard" size="md" />
            <AnalysisDepthControl value="deep" size="md" />
          </div>
        </div>

        {/* Combined Form */}
        <div className="flex flex-col gap-4">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            ANALYSIS RESULT CARD
          </div>

          <div
            className="flex flex-col gap-4 p-4 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div className="flex items-center justify-between">
              <div style={{ fontSize: '14px', fontWeight: 600, color: '#F1F5F9' }}>
                Contract Analysis Complete
              </div>
              <RiskBadge risk="medium" size="md" />
            </div>

            <div className="flex items-center gap-2">
              <div style={{ fontSize: '11px', color: '#475569' }}>Depth:</div>
              <AnalysisDepthControl value="deep" size="sm" />
            </div>

            <div style={{ fontSize: '12px', color: '#94A3B8', lineHeight: 1.5 }}>
              Found 3 clauses requiring review. Medium risk factors identified in termination section.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
