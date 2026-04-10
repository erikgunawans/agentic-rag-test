import { ColumnHeader } from './shared';

export function ColumnHeaderReference() {
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
          Column Header{' '}
          <span
            style={{
              background: 'linear-gradient(to right, #7C5CFC, #A78BFA, #60A5FA)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text'
            }}
          >
            Component
          </span>
        </h1>
        <p style={{ fontSize: '14px', color: '#94A3B8' }}>
          Reusable Column 2 header applied across all 6 Knowledge Hub pages
        </p>
      </div>

      {/* Component Specification */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl mx-auto"
        style={{
          maxWidth: '800px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '16px', fontWeight: 600, color: '#F1F5F9' }}>
          Component Specification
        </div>

        <div className="flex flex-col gap-3">
          <div className="flex items-start gap-4">
            <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '100px' }}>
              HEIGHT
            </div>
            <div style={{ fontSize: '12px', color: '#94A3B8' }}>64px</div>
          </div>

          <div className="flex items-start gap-4">
            <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '100px' }}>
              BACKGROUND
            </div>
            <div style={{ fontSize: '12px', color: '#94A3B8', fontFamily: 'monospace' }}>#0F1829</div>
          </div>

          <div className="flex items-start gap-4">
            <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '100px' }}>
              LAYOUT
            </div>
            <div style={{ fontSize: '12px', color: '#94A3B8' }}>Horizontal, centered alignment</div>
          </div>

          <div className="flex items-start gap-4">
            <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '100px' }}>
              PADDING
            </div>
            <div style={{ fontSize: '12px', color: '#94A3B8' }}>0 20px</div>
          </div>

          <div className="flex items-start gap-4">
            <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '100px' }}>
              BORDER
            </div>
            <div style={{ fontSize: '12px', color: '#94A3B8', fontFamily: 'monospace' }}>
              border-bottom: 1px solid #1E2D45
            </div>
          </div>
        </div>
      </div>

      {/* All 6 Page Headers */}
      <div className="grid grid-cols-2 gap-6" style={{ maxWidth: '1200px', margin: '0 auto' }}>
        {/* 1. Knowledge Hub (Chat) */}
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
              1
            </div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
              Knowledge Hub
            </div>
          </div>

          <ColumnHeader 
            title="Knowledge Hub" 
            subtitle="Chat History" 
            rightIcon="chevron-left"
          />

          <div className="p-4" style={{ backgroundColor: '#162033' }}>
            <div
              className="p-3 rounded-lg"
              style={{
                backgroundColor: '#0F1829',
                border: '1px solid #1E2D45',
                fontFamily: 'monospace',
                fontSize: '11px',
                color: '#94A3B8'
              }}
            >
              <div style={{ marginBottom: '4px', color: '#7C5CFC' }}>
                &lt;ColumnHeader
              </div>
              <div style={{ marginLeft: '12px' }}>
                title=&quot;Knowledge Hub&quot;
              </div>
              <div style={{ marginLeft: '12px' }}>
                subtitle=&quot;Chat History&quot;
              </div>
              <div style={{ marginLeft: '12px' }}>
                rightIcon=&quot;chevron-left&quot;
              </div>
              <div style={{ color: '#7C5CFC' }}>
                /&gt;
              </div>
            </div>
          </div>
        </div>

        {/* 2. Documents */}
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
              2
            </div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
              Documents
            </div>
          </div>

          <ColumnHeader 
            title="Documents" 
            subtitle="Library & Upload" 
            rightIcon="settings"
          />

          <div className="p-4" style={{ backgroundColor: '#162033' }}>
            <div
              className="p-3 rounded-lg"
              style={{
                backgroundColor: '#0F1829',
                border: '1px solid #1E2D45',
                fontFamily: 'monospace',
                fontSize: '11px',
                color: '#94A3B8'
              }}
            >
              <div style={{ marginBottom: '4px', color: '#22D3EE' }}>
                &lt;ColumnHeader
              </div>
              <div style={{ marginLeft: '12px' }}>
                title=&quot;Documents&quot;
              </div>
              <div style={{ marginLeft: '12px' }}>
                subtitle=&quot;Library &amp; Upload&quot;
              </div>
              <div style={{ marginLeft: '12px' }}>
                rightIcon=&quot;settings&quot;
              </div>
              <div style={{ color: '#22D3EE' }}>
                /&gt;
              </div>
            </div>
          </div>
        </div>

        {/* 3. Create Document */}
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
              3
            </div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
              Create Document
            </div>
          </div>

          <ColumnHeader 
            title="Create Document" 
            subtitle="Form & Templates" 
            rightIcon="close"
          />

          <div className="p-4" style={{ backgroundColor: '#162033' }}>
            <div
              className="p-3 rounded-lg"
              style={{
                backgroundColor: '#0F1829',
                border: '1px solid #1E2D45',
                fontFamily: 'monospace',
                fontSize: '11px',
                color: '#94A3B8'
              }}
            >
              <div style={{ marginBottom: '4px', color: '#7C5CFC' }}>
                &lt;ColumnHeader
              </div>
              <div style={{ marginLeft: '12px' }}>
                title=&quot;Create Document&quot;
              </div>
              <div style={{ marginLeft: '12px' }}>
                subtitle=&quot;Form &amp; Templates&quot;
              </div>
              <div style={{ marginLeft: '12px' }}>
                rightIcon=&quot;close&quot;
              </div>
              <div style={{ color: '#7C5CFC' }}>
                /&gt;
              </div>
            </div>
          </div>
        </div>

        {/* 4. Compare Documents */}
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
              4
            </div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
              Compare Documents
            </div>
          </div>

          <ColumnHeader 
            title="Compare Documents" 
            subtitle="Side-by-Side Analysis" 
            rightIcon="arrow-left"
          />

          <div className="p-4" style={{ backgroundColor: '#162033' }}>
            <div
              className="p-3 rounded-lg"
              style={{
                backgroundColor: '#0F1829',
                border: '1px solid #1E2D45',
                fontFamily: 'monospace',
                fontSize: '11px',
                color: '#94A3B8'
              }}
            >
              <div style={{ marginBottom: '4px', color: '#22D3EE' }}>
                &lt;ColumnHeader
              </div>
              <div style={{ marginLeft: '12px' }}>
                title=&quot;Compare Documents&quot;
              </div>
              <div style={{ marginLeft: '12px' }}>
                subtitle=&quot;Side-by-Side Analysis&quot;
              </div>
              <div style={{ marginLeft: '12px' }}>
                rightIcon=&quot;arrow-left&quot;
              </div>
              <div style={{ color: '#22D3EE' }}>
                /&gt;
              </div>
            </div>
          </div>
        </div>

        {/* 5. Compliance Check */}
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
              5
            </div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
              Compliance Check
            </div>
          </div>

          <ColumnHeader 
            title="Compliance Check" 
            subtitle="Regulatory Validation" 
            rightIcon="close"
          />

          <div className="p-4" style={{ backgroundColor: '#162033' }}>
            <div
              className="p-3 rounded-lg"
              style={{
                backgroundColor: '#0F1829',
                border: '1px solid #1E2D45',
                fontFamily: 'monospace',
                fontSize: '11px',
                color: '#94A3B8'
              }}
            >
              <div style={{ marginBottom: '4px', color: '#34D399' }}>
                &lt;ColumnHeader
              </div>
              <div style={{ marginLeft: '12px' }}>
                title=&quot;Compliance Check&quot;
              </div>
              <div style={{ marginLeft: '12px' }}>
                subtitle=&quot;Regulatory Validation&quot;
              </div>
              <div style={{ marginLeft: '12px' }}>
                rightIcon=&quot;close&quot;
              </div>
              <div style={{ color: '#34D399' }}>
                /&gt;
              </div>
            </div>
          </div>
        </div>

        {/* 6. Contract Analysis */}
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
                backgroundColor: 'rgba(245, 158, 11, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '12px',
                fontWeight: 700,
                color: '#F59E0B'
              }}
            >
              6
            </div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
              Contract Analysis
            </div>
          </div>

          <ColumnHeader 
            title="Contract Analysis" 
            subtitle="Risk & Clause Detection" 
            rightIcon="arrow-left"
          />

          <div className="p-4" style={{ backgroundColor: '#162033' }}>
            <div
              className="p-3 rounded-lg"
              style={{
                backgroundColor: '#0F1829',
                border: '1px solid #1E2D45',
                fontFamily: 'monospace',
                fontSize: '11px',
                color: '#94A3B8'
              }}
            >
              <div style={{ marginBottom: '4px', color: '#F59E0B' }}>
                &lt;ColumnHeader
              </div>
              <div style={{ marginLeft: '12px' }}>
                title=&quot;Contract Analysis&quot;
              </div>
              <div style={{ marginLeft: '12px' }}>
                subtitle=&quot;Risk &amp; Clause Detection&quot;
              </div>
              <div style={{ marginLeft: '12px' }}>
                rightIcon=&quot;arrow-left&quot;
              </div>
              <div style={{ color: '#F59E0B' }}>
                /&gt;
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Icon Variant Reference */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl mx-auto"
        style={{
          maxWidth: '800px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '16px', fontWeight: 600, color: '#F1F5F9' }}>
          Right Icon Variants
        </div>

        <div className="grid grid-cols-5 gap-3">
          {[
            { variant: 'chevron-left', label: 'Chevron Left', usage: 'Navigation back' },
            { variant: 'close', label: 'Close (X)', usage: 'Exit/Close panel' },
            { variant: 'arrow-left', label: 'Arrow Left', usage: 'Return to previous' },
            { variant: 'settings', label: 'Settings', usage: 'Configuration' },
            { variant: 'none', label: 'None', usage: 'No icon shown' }
          ].map(({ variant, label, usage }) => (
            <div
              key={variant}
              className="flex flex-col gap-2 p-3 rounded-lg"
              style={{
                backgroundColor: '#162033',
                border: '1px solid #1E2D45'
              }}
            >
              <div style={{ fontSize: '11px', fontWeight: 600, color: '#7C5CFC', fontFamily: 'monospace' }}>
                &quot;{variant}&quot;
              </div>
              <div style={{ fontSize: '11px', color: '#94A3B8' }}>
                {label}
              </div>
              <div style={{ fontSize: '10px', color: '#475569' }}>
                {usage}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Properties Table */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl mx-auto"
        style={{
          maxWidth: '800px',
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
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#7C5CFC', minWidth: '140px' }}>
              title
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', color: '#F1F5F9' }}>
                string (required)
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                Main heading text for the column
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
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#7C5CFC', minWidth: '140px' }}>
              subtitle
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', color: '#F1F5F9' }}>
                string (optional)
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                Secondary descriptive text below the title
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
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#7C5CFC', minWidth: '140px' }}>
              rightIcon
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', color: '#F1F5F9' }}>
                RightIconVariant (optional)
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                Icon variant to display on the right. Default: 'chevron-left'
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
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#7C5CFC', minWidth: '140px' }}>
              onRightIconClick
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <div style={{ fontSize: '12px', color: '#F1F5F9' }}>
                () =&gt; void (optional)
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                Callback function when the right icon is clicked
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
