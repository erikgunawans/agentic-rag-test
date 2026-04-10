import { useState } from 'react';
import { IconRailNew } from './shared';
import { 
  MessageSquare, 
  Folder, 
  FilePlus, 
  GitCompare, 
  ShieldCheck, 
  Scale,
  LayoutGrid,
  BarChart3,
  Users,
  Bell,
  Settings
} from 'lucide-react';

export function IconRailGroupReference() {
  const [variant, setVariant] = useState<'closed' | 'open' | 'hovered' | 'sub-active'>('closed');
  const [activeMainId, setActiveMainId] = useState<string>('chat');
  const [activeGroupId, setActiveGroupId] = useState<string | null>(null);

  // Main icons for the rail
  const mainIcons = [
    { icon: MessageSquare, id: 'chat', label: 'Knowledge Hub' },
    { icon: Folder, id: 'documents', label: 'Documents' },
    { icon: FilePlus, id: 'create', label: 'Create Document' },
    { icon: GitCompare, id: 'compare', label: 'Compare Documents' },
    { icon: ShieldCheck, id: 'compliance', label: 'Compliance Check' },
    { icon: Scale, id: 'contract', label: 'Contract Analysis' }
  ];

  // Group items
  const groupItems = [
    { id: 'analytics', icon: BarChart3, label: 'Analytics' },
    { id: 'team', icon: Users, label: 'Team Access' },
    { id: 'notifications', icon: Bell, label: 'Notifications' },
    { id: 'settings', icon: Settings, label: 'Settings' }
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
          Icon Rail{' '}
          <span
            style={{
              background: 'linear-gradient(to right, #7C5CFC, #A78BFA, #60A5FA)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text'
            }}
          >
            Expandable Group
          </span>
        </h1>
        <p style={{ fontSize: '14px', color: '#94A3B8' }}>
          Updated 60px icon rail with collapsible group panel
        </p>
      </div>

      {/* Component Specification */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl mx-auto"
        style={{
          maxWidth: '1000px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '16px', fontWeight: 600, color: '#F1F5F9' }}>
          Component Specification
        </div>

        <div className="grid grid-cols-2 gap-6">
          <div className="flex flex-col gap-3">
            <div className="flex items-start gap-4">
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '120px' }}>
                RAIL WIDTH
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8' }}>60px container, 56px pill</div>
            </div>

            <div className="flex items-start gap-4">
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '120px' }}>
                FIXED ICONS
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8' }}>6 main navigation icons</div>
            </div>

            <div className="flex items-start gap-4">
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '120px' }}>
                DIVIDER
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8' }}>20px × 1px, #1E2D45</div>
            </div>

            <div className="flex items-start gap-4">
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '120px' }}>
                GROUP TRIGGER
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8' }}>LayoutGrid icon, 3 states</div>
            </div>
          </div>

          <div className="flex flex-col gap-3">
            <div className="flex items-start gap-4">
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '120px' }}>
                PANEL WIDTH
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8' }}>220px, auto height</div>
            </div>

            <div className="flex items-start gap-4">
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '120px' }}>
                PANEL GAP
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8' }}>10px from rail edge</div>
            </div>

            <div className="flex items-start gap-4">
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '120px' }}>
                GROUP ITEMS
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8' }}>4 modules in panel</div>
            </div>

            <div className="flex items-start gap-4">
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#475569', minWidth: '120px' }}>
                ANIMATION
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8' }}>200ms slide + fade</div>
            </div>
          </div>
        </div>
      </div>

      {/* Group Trigger States */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl mx-auto"
        style={{
          maxWidth: '1000px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '16px', fontWeight: 600, color: '#F1F5F9' }}>
          Group Trigger Icon — 3 States
        </div>

        <div className="grid grid-cols-3 gap-4">
          {/* State A - Collapsed */}
          <div
            className="flex flex-col items-center gap-4 p-5 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div
              className="flex items-center justify-center rounded-lg"
              style={{
                width: '36px',
                height: '36px',
                backgroundColor: 'transparent',
                color: '#94A3B8'
              }}
            >
              <LayoutGrid size={20} />
            </div>
            <div className="flex flex-col items-center gap-1">
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
                State A: Collapsed
              </div>
              <div style={{ fontSize: '11px', color: '#64748B', textAlign: 'center' }}>
                Default state, no background
              </div>
            </div>
            <div
              className="px-3 py-1 rounded-md"
              style={{
                backgroundColor: 'rgba(148, 163, 184, 0.1)',
                border: '1px solid rgba(148, 163, 184, 0.2)'
              }}
            >
              <div style={{ fontSize: '10px', fontFamily: 'monospace', color: '#94A3B8' }}>
                default
              </div>
            </div>
          </div>

          {/* State B - Expanded */}
          <div
            className="flex flex-col items-center gap-4 p-5 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div
              className="relative flex items-center justify-center rounded-lg"
              style={{
                width: '36px',
                height: '36px',
                backgroundColor: 'rgba(124, 92, 252, 0.12)',
                color: '#7C5CFC',
                boxShadow: '0 0 16px rgba(124, 92, 252, 0.3)'
              }}
            >
              <LayoutGrid size={20} />
              {/* Indicator dot */}
              <div
                className="absolute"
                style={{
                  top: '6px',
                  right: '6px',
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: '#7C5CFC'
                }}
              />
            </div>
            <div className="flex flex-col items-center gap-1">
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
                State B: Expanded
              </div>
              <div style={{ fontSize: '11px', color: '#64748B', textAlign: 'center' }}>
                Panel open, with glow + dot
              </div>
            </div>
            <div
              className="px-3 py-1 rounded-md"
              style={{
                backgroundColor: 'rgba(124, 92, 252, 0.15)',
                border: '1px solid rgba(124, 92, 252, 0.3)'
              }}
            >
              <div style={{ fontSize: '10px', fontFamily: 'monospace', color: '#7C5CFC' }}>
                active
              </div>
            </div>
          </div>

          {/* State C - Sub-page Active */}
          <div
            className="flex flex-col items-center gap-4 p-5 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div
              className="flex items-center justify-center rounded-lg"
              style={{
                width: '36px',
                height: '36px',
                backgroundColor: 'rgba(124, 92, 252, 0.08)',
                color: '#7C5CFC'
              }}
            >
              <LayoutGrid size={20} />
            </div>
            <div className="flex flex-col items-center gap-1">
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
                State C: Sub-Active
              </div>
              <div style={{ fontSize: '11px', color: '#64748B', textAlign: 'center' }}>
                Child page active, subtle bg
              </div>
            </div>
            <div
              className="px-3 py-1 rounded-md"
              style={{
                backgroundColor: 'rgba(124, 92, 252, 0.1)',
                border: '1px solid rgba(124, 92, 252, 0.2)'
              }}
            >
              <div style={{ fontSize: '10px', fontFamily: 'monospace', color: '#7C5CFC' }}>
                subtle
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Panel Item States */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl mx-auto"
        style={{
          maxWidth: '1000px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '16px', fontWeight: 600, color: '#F1F5F9' }}>
          Panel Item States
        </div>

        <div className="grid grid-cols-3 gap-4">
          {/* Default State */}
          <div
            className="flex flex-col gap-3 p-4 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div style={{ fontSize: '12px', fontWeight: 600, color: '#94A3B8', textAlign: 'center' }}>
              Default State
            </div>
            <div
              className="flex items-center gap-2.5 px-3 rounded-[10px]"
              style={{
                height: '40px',
                backgroundColor: 'transparent'
              }}
            >
              <BarChart3 size={18} style={{ color: '#94A3B8' }} />
              <div style={{ fontSize: '13px', fontWeight: 500, color: '#94A3B8' }}>
                Analytics
              </div>
            </div>
          </div>

          {/* Hover State */}
          <div
            className="flex flex-col gap-3 p-4 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div style={{ fontSize: '12px', fontWeight: 600, color: '#94A3B8', textAlign: 'center' }}>
              Hover State
            </div>
            <div
              className="flex items-center gap-2.5 px-3 rounded-[10px]"
              style={{
                height: '40px',
                backgroundColor: '#1C2840'
              }}
            >
              <BarChart3 size={18} style={{ color: '#F1F5F9' }} />
              <div style={{ fontSize: '13px', fontWeight: 500, color: '#F1F5F9' }}>
                Analytics
              </div>
            </div>
          </div>

          {/* Active State */}
          <div
            className="flex flex-col gap-3 p-4 rounded-xl"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div style={{ fontSize: '12px', fontWeight: 600, color: '#94A3B8', textAlign: 'center' }}>
              Active State
            </div>
            <div
              className="relative flex items-center gap-2.5 px-3 rounded-[10px]"
              style={{
                height: '40px',
                backgroundColor: 'rgba(124, 92, 252, 0.12)'
              }}
            >
              {/* Left accent bar */}
              <div
                className="absolute left-0 rounded-r"
                style={{
                  width: '3px',
                  height: '20px',
                  backgroundColor: '#7C5CFC',
                  borderRadius: '0 2px 2px 0'
                }}
              />
              <BarChart3 size={18} style={{ color: '#7C5CFC' }} />
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#7C5CFC' }}>
                Analytics
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Variant Selector */}
      <div
        className="flex items-center justify-center gap-3 p-4 rounded-xl mx-auto"
        style={{
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '13px', fontWeight: 600, color: '#94A3B8' }}>
          Interactive Demo:
        </div>
        {[
          { id: 'closed', label: 'Panel Closed' },
          { id: 'open', label: 'Panel Open' },
          { id: 'sub-active', label: 'Sub-Page Active' }
        ].map((v) => (
          <button
            key={v.id}
            onClick={() => {
              setVariant(v.id as any);
              if (v.id === 'sub-active') {
                setActiveGroupId('analytics');
              } else {
                setActiveGroupId(null);
              }
            }}
            className="px-4 py-2 rounded-lg transition-all duration-200"
            style={{
              backgroundColor: variant === v.id ? 'rgba(124, 92, 252, 0.12)' : '#162033',
              border: variant === v.id ? '1px solid rgba(124, 92, 252, 0.4)' : '1px solid #1E2D45',
              fontSize: '12px',
              fontWeight: 600,
              color: variant === v.id ? '#7C5CFC' : '#94A3B8'
            }}
          >
            {v.label}
          </button>
        ))}
      </div>

      {/* Live Demo - 4 Variants in Grid */}
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
          Live Interactive Component
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

      {/* Live Component Demo */}
      <div
        className="flex justify-center p-8 rounded-2xl mx-auto"
        style={{
          minWidth: '400px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <IconRailNew
          mainIcons={mainIcons.map((item) => ({
            ...item,
            isActive: item.id === activeMainId,
            onClick: () => {
              setActiveMainId(item.id);
              setActiveGroupId(null);
            }
          }))}
          groupItems={groupItems}
          activeGroupItemId={activeGroupId}
          onGroupItemClick={(id) => {
            setActiveGroupId(id);
            setActiveMainId('');
          }}
          userInitials="AS"
          userOnline={true}
        />
      </div>

      {/* Group Items Reference */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl mx-auto"
        style={{
          maxWidth: '1000px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '16px', fontWeight: 600, color: '#F1F5F9' }}>
          Group Panel Items (4 Modules)
        </div>

        <div className="grid grid-cols-2 gap-4">
          {groupItems.map((item) => {
            const ItemIcon = item.icon;
            return (
              <div
                key={item.id}
                className="flex items-center gap-3 p-4 rounded-xl"
                style={{
                  backgroundColor: '#162033',
                  border: '1px solid #1E2D45'
                }}
              >
                <div
                  className="flex items-center justify-center rounded-lg"
                  style={{
                    width: '40px',
                    height: '40px',
                    backgroundColor: '#0F1829',
                    border: '1px solid #1E2D45'
                  }}
                >
                  <ItemIcon size={20} style={{ color: '#94A3B8' }} />
                </div>
                <div className="flex flex-col gap-1">
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
                    {item.label}
                  </div>
                  <div
                    style={{
                      fontSize: '10px',
                      fontFamily: 'monospace',
                      color: '#7C5CFC'
                    }}
                  >
                    &quot;{item.id}&quot;
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Integration Notes */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl mx-auto"
        style={{
          maxWidth: '1000px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '16px', fontWeight: 600, color: '#F1F5F9' }}>
          Integration Notes
        </div>

        <div className="flex flex-col gap-3">
          <div
            className="flex items-start gap-3 p-4 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div
              className="flex items-center justify-center rounded-md"
              style={{
                width: '24px',
                height: '24px',
                backgroundColor: 'rgba(124, 92, 252, 0.12)',
                fontSize: '12px',
                fontWeight: 700,
                color: '#7C5CFC'
              }}
            >
              1
            </div>
            <div className="flex-1">
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9', marginBottom: '4px' }}>
                Updated Icon Rail Structure
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8', lineHeight: 1.6 }}>
                All 6 existing page frames now use the updated IconRailNew component with the expandable group section
              </div>
            </div>
          </div>

          <div
            className="flex items-start gap-3 p-4 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div
              className="flex items-center justify-center rounded-md"
              style={{
                width: '24px',
                height: '24px',
                backgroundColor: 'rgba(124, 92, 252, 0.12)',
                fontSize: '12px',
                fontWeight: 700,
                color: '#7C5CFC'
              }}
            >
              2
            </div>
            <div className="flex-1">
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9', marginBottom: '4px' }}>
                Removed Icons from Main Rail
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8', lineHeight: 1.6 }}>
                Reference pages (Form Variants, Text Inputs, etc.) are now accessed through the expandable group panel
              </div>
            </div>
          </div>

          <div
            className="flex items-start gap-3 p-4 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div
              className="flex items-center justify-center rounded-md"
              style={{
                width: '24px',
                height: '24px',
                backgroundColor: 'rgba(124, 92, 252, 0.12)',
                fontSize: '12px',
                fontWeight: 700,
                color: '#7C5CFC'
              }}
            >
              3
            </div>
            <div className="flex-1">
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9', marginBottom: '4px' }}>
                Panel Behavior
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8', lineHeight: 1.6 }}>
                Click outside panel or close button to dismiss. 200ms slide animation with fade effect
              </div>
            </div>
          </div>

          <div
            className="flex items-start gap-3 p-4 rounded-lg"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45'
            }}
          >
            <div
              className="flex items-center justify-center rounded-md"
              style={{
                width: '24px',
                height: '24px',
                backgroundColor: 'rgba(124, 92, 252, 0.12)',
                fontSize: '12px',
                fontWeight: 700,
                color: '#7C5CFC'
              }}
            >
              4
            </div>
            <div className="flex-1">
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9', marginBottom: '4px' }}>
                State Management
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8', lineHeight: 1.6 }}>
                Group trigger shows State C (sub-active) when a child page is currently active, even with panel closed
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
