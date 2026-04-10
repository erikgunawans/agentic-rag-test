import { Home, Folder, FilePlus, GitCompare, ShieldCheck, Scale } from 'lucide-react';
import { IconRailMaster, IconSlot } from './IconRailMaster';

export function IconRailReference() {
  // Define the 6 icon slots
  const iconSlots: IconSlot[] = [
    { Icon: Home, id: 0, label: 'Chat' },
    { Icon: Folder, id: 1, label: 'Documents' },
    { Icon: FilePlus, id: 2, label: 'Create Document' },
    { Icon: GitCompare, id: 3, label: 'Compare Documents' },
    { Icon: ShieldCheck, id: 4, label: 'Compliance Check' },
    { Icon: Scale, id: 5, label: 'Contract Analysis' }
  ];

  return (
    <div
      className="flex flex-col gap-8 p-8"
      style={{
        backgroundColor: '#0B1120',
        minHeight: '100vh'
      }}
    >
      {/* Header */}
      <div className="flex flex-col items-center gap-3">
        <h1
          style={{
            fontSize: '32px',
            fontWeight: 700,
            color: '#F1F5F9',
            letterSpacing: '-0.02em'
          }}
        >
          Icon Rail{' '}
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
          6 icon slots with Default and Active variants
        </p>
      </div>

      {/* Component Specifications */}
      <div
        className="flex gap-6 p-6 rounded-2xl mx-auto"
        style={{
          width: 'fit-content',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        {/* Active State Specs */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            ACTIVE STATE
          </div>
          <div className="flex flex-col gap-2" style={{ fontSize: '12px', color: '#94A3B8' }}>
            <div className="flex items-center gap-3">
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  backgroundColor: 'rgba(124, 92, 252, 0.12)',
                  borderRadius: '8px',
                  boxShadow: '0 0 16px rgba(124, 92, 252, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#7C5CFC'
                }}
              >
                <Home size={20} />
              </div>
              <div className="flex flex-col gap-1">
                <div style={{ fontSize: '11px', color: '#64748B', fontFamily: 'monospace' }}>
                  bg: rgba(124,92,252,0.12)
                </div>
                <div style={{ fontSize: '11px', color: '#64748B', fontFamily: 'monospace' }}>
                  icon: #7C5CFC
                </div>
                <div style={{ fontSize: '11px', color: '#64748B', fontFamily: 'monospace' }}>
                  shadow: 0 0 16px rgba(124,92,252,0.3)
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Default State Specs */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            DEFAULT STATE
          </div>
          <div className="flex flex-col gap-2" style={{ fontSize: '12px', color: '#94A3B8' }}>
            <div className="flex items-center gap-3">
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  backgroundColor: 'transparent',
                  borderRadius: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#94A3B8'
                }}
              >
                <Folder size={20} />
              </div>
              <div className="flex flex-col gap-1">
                <div style={{ fontSize: '11px', color: '#64748B', fontFamily: 'monospace' }}>
                  bg: transparent
                </div>
                <div style={{ fontSize: '11px', color: '#64748B', fontFamily: 'monospace' }}>
                  icon: #94A3B8
                </div>
                <div style={{ fontSize: '11px', color: '#64748B', fontFamily: 'monospace' }}>
                  shadow: none
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Size Specs */}
        <div className="flex flex-col gap-3">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            DIMENSIONS
          </div>
          <div className="flex flex-col gap-1" style={{ fontSize: '11px', color: '#64748B', fontFamily: 'monospace' }}>
            <div>Icon slot: 36×36px</div>
            <div>Icon size: 20px</div>
            <div>Border radius: 8px</div>
            <div>Rail width: 88px (floating)</div>
            <div>Rail width: 60px (compact)</div>
            <div>Pill width: 56px</div>
          </div>
        </div>
      </div>

      {/* Reference Sheet - All 6 Active Instances */}
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
            Active State Reference Sheet
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

        {/* Grid of all 6 instances - Floating Style */}
        <div>
          <div
            className="flex items-center justify-center gap-2 mb-4"
            style={{
              fontSize: '13px',
              fontWeight: 600,
              color: '#94A3B8',
              letterSpacing: '0.05em'
            }}
          >
            FLOATING PILL VARIANT
          </div>
          <div
            className="grid gap-6"
            style={{
              gridTemplateColumns: 'repeat(6, 1fr)',
              maxWidth: '1200px',
              margin: '0 auto'
            }}
          >
            {iconSlots.map((slot) => (
              <div
                key={`floating-${slot.id}`}
                className="flex flex-col gap-4 p-4 rounded-2xl"
                style={{
                  backgroundColor: '#0F1829',
                  border: '1px solid #1E2D45'
                }}
              >
                {/* Label */}
                <div className="flex flex-col items-center gap-2">
                  <div
                    className="flex items-center justify-center rounded-lg"
                    style={{
                      width: '32px',
                      height: '32px',
                      backgroundColor: 'rgba(124, 92, 252, 0.15)',
                      border: '1px solid rgba(124, 92, 252, 0.3)',
                      fontSize: '14px',
                      fontWeight: 700,
                      color: '#7C5CFC'
                    }}
                  >
                    {slot.id + 1}
                  </div>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: '#F1F5F9', textAlign: 'center' }}>
                    {slot.label}
                  </div>
                  <div style={{ fontSize: '10px', color: '#475569', fontFamily: 'monospace' }}>
                    activeSlotId: {slot.id}
                  </div>
                </div>

                {/* Icon Rail Instance */}
                <div
                  className="flex items-center justify-center rounded-xl"
                  style={{
                    height: '480px',
                    backgroundColor: '#0B1120',
                    border: '1px solid #1E2D45'
                  }}
                >
                  <IconRailMaster
                    slots={iconSlots}
                    activeSlotId={slot.id}
                    showLabels={false}
                    size="floating"
                  />
                </div>

                {/* Active Icon Label */}
                <div
                  className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg"
                  style={{
                    backgroundColor: '#162033',
                    border: '1px solid #1E2D45'
                  }}
                >
                  <slot.Icon size={14} style={{ color: '#7C5CFC' }} />
                  <span style={{ fontSize: '11px', color: '#94A3B8' }}>Active</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Grid of all 6 instances - Compact Style */}
        <div className="mt-8">
          <div
            className="flex items-center justify-center gap-2 mb-4"
            style={{
              fontSize: '13px',
              fontWeight: 600,
              color: '#94A3B8',
              letterSpacing: '0.05em'
            }}
          >
            COMPACT VARIANT
          </div>
          <div
            className="grid gap-6"
            style={{
              gridTemplateColumns: 'repeat(6, 1fr)',
              maxWidth: '1200px',
              margin: '0 auto'
            }}
          >
            {iconSlots.map((slot) => (
              <div
                key={`compact-${slot.id}`}
                className="flex flex-col gap-4 p-4 rounded-2xl"
                style={{
                  backgroundColor: '#0F1829',
                  border: '1px solid #1E2D45'
                }}
              >
                {/* Label */}
                <div className="flex flex-col items-center gap-2">
                  <div
                    className="flex items-center justify-center rounded-lg"
                    style={{
                      width: '32px',
                      height: '32px',
                      backgroundColor: 'rgba(34, 211, 238, 0.15)',
                      border: '1px solid rgba(34, 211, 238, 0.3)',
                      fontSize: '14px',
                      fontWeight: 700,
                      color: '#22D3EE'
                    }}
                  >
                    {slot.id + 1}
                  </div>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: '#F1F5F9', textAlign: 'center' }}>
                    {slot.label}
                  </div>
                  <div style={{ fontSize: '10px', color: '#475569', fontFamily: 'monospace' }}>
                    size: compact
                  </div>
                </div>

                {/* Icon Rail Instance */}
                <div
                  className="flex items-center justify-center rounded-xl"
                  style={{
                    height: '480px',
                    backgroundColor: '#080C14',
                    border: '1px solid #1E2D45'
                  }}
                >
                  <IconRailMaster
                    slots={iconSlots}
                    activeSlotId={slot.id}
                    showLabels={false}
                    size="compact"
                  />
                </div>

                {/* Active Icon Label */}
                <div
                  className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg"
                  style={{
                    backgroundColor: '#162033',
                    border: '1px solid #1E2D45'
                  }}
                >
                  <slot.Icon size={14} style={{ color: '#7C5CFC' }} />
                  <span style={{ fontSize: '11px', color: '#94A3B8' }}>Active</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Usage Code Examples */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl mx-auto"
        style={{
          maxWidth: '900px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '14px', fontWeight: 600, color: '#F1F5F9', marginBottom: '8px' }}>
          Usage Examples
        </div>

        {/* Example 1 */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            FLOATING PILL WITH HOME ACTIVE
          </div>
          <div
            className="p-4 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45',
              fontFamily: 'monospace',
              fontSize: '12px',
              color: '#94A3B8',
              overflowX: 'auto'
            }}
          >
            <pre style={{ margin: 0 }}>
{`<IconRailMaster
  slots={iconSlots}
  activeSlotId={0}
  size="floating"
/>`}
            </pre>
          </div>
        </div>

        {/* Example 2 */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            COMPACT WITH DOCUMENTS ACTIVE
          </div>
          <div
            className="p-4 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45',
              fontFamily: 'monospace',
              fontSize: '12px',
              color: '#94A3B8',
              overflowX: 'auto'
            }}
          >
            <pre style={{ margin: 0 }}>
{`<IconRailMaster
  slots={iconSlots}
  activeSlotId={1}
  size="compact"
/>`}
            </pre>
          </div>
        </div>

        {/* Example 3 */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            WITH CLICK HANDLER
          </div>
          <div
            className="p-4 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45',
              fontFamily: 'monospace',
              fontSize: '12px',
              color: '#94A3B8',
              overflowX: 'auto'
            }}
          >
            <pre style={{ margin: 0 }}>
{`<IconRailMaster
  slots={iconSlots}
  activeSlotId={activeId}
  onSlotClick={(id) => setActiveId(id)}
  showLabels={true}
  size="floating"
/>`}
            </pre>
          </div>
        </div>
      </div>

      {/* Component Properties Table */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl mx-auto"
        style={{
          maxWidth: '900px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '14px', fontWeight: 600, color: '#F1F5F9', marginBottom: '8px' }}>
          Component Properties
        </div>

        <div className="flex flex-col gap-3">
          {/* Property 1 */}
          <div
            className="flex items-start gap-4 p-3 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#7C5CFC', minWidth: '120px' }}>
              slots
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', color: '#F1F5F9' }}>
                IconSlot[]
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                Array of icon configurations with Icon, id, and optional label
              </div>
            </div>
          </div>

          {/* Property 2 */}
          <div
            className="flex items-start gap-4 p-3 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#7C5CFC', minWidth: '120px' }}>
              activeSlotId
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', color: '#F1F5F9' }}>
                number
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                ID of the currently active slot (0-5)
              </div>
            </div>
          </div>

          {/* Property 3 */}
          <div
            className="flex items-start gap-4 p-3 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#7C5CFC', minWidth: '120px' }}>
              onSlotClick
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', color: '#F1F5F9' }}>
                (id: number) =&gt; void
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                Optional callback when a slot is clicked
              </div>
            </div>
          </div>

          {/* Property 4 */}
          <div
            className="flex items-start gap-4 p-3 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#7C5CFC', minWidth: '120px' }}>
              showLabels
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', color: '#F1F5F9' }}>
                boolean
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                Show tooltips on hover (default: false)
              </div>
            </div>
          </div>

          {/* Property 5 */}
          <div
            className="flex items-start gap-4 p-3 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#7C5CFC', minWidth: '120px' }}>
              size
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', color: '#F1F5F9' }}>
                'compact' | 'floating'
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                Variant style: floating pill (88px) or compact (60px) - default: 'floating'
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
