import { useState, useRef, useEffect } from 'react';
import { 
  LucideIcon, 
  Sparkles, 
  LayoutGrid,
  X,
  BarChart3,
  Users,
  Bell,
  Settings
} from 'lucide-react';

export interface GroupItem {
  id: string;
  icon: LucideIcon;
  label: string;
  isActive?: boolean;
}

export interface IconRailNewProps {
  mainIcons: Array<{
    icon: LucideIcon;
    id: string;
    isActive: boolean;
    onClick: () => void;
  }>;
  groupItems?: GroupItem[];
  activeGroupItemId?: string | null;
  onGroupItemClick?: (id: string) => void;
  userInitials?: string;
  userOnline?: boolean;
}

export function IconRailNew({
  mainIcons,
  groupItems = [
    { id: 'analytics', icon: BarChart3, label: 'Analytics' },
    { id: 'team', icon: Users, label: 'Team Access' },
    { id: 'notifications', icon: Bell, label: 'Notifications' },
    { id: 'settings', icon: Settings, label: 'Settings' }
  ],
  activeGroupItemId = null,
  onGroupItemClick,
  userInitials = 'AS',
  userOnline = true
}: IconRailNewProps) {
  const [isGroupOpen, setIsGroupOpen] = useState(false);
  const [hoveredGroupItem, setHoveredGroupItem] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Close panel when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        isGroupOpen &&
        panelRef.current &&
        triggerRef.current &&
        !panelRef.current.contains(event.target as Node) &&
        !triggerRef.current.contains(event.target as Node)
      ) {
        setIsGroupOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isGroupOpen]);

  const hasActiveSubPage = !!activeGroupItemId;
  const groupTriggerState = isGroupOpen ? 'expanded' : hasActiveSubPage ? 'sub-active' : 'collapsed';

  return (
    <div className="relative flex items-center justify-center" style={{ width: '60px' }}>
      {/* Icon Rail Container */}
      <div
        className="flex flex-col items-center gap-1.5 py-3 rounded-[28px]"
        style={{
          width: '56px',
          backgroundColor: 'rgba(15, 24, 41, 0.7)',
          backdropFilter: 'blur(24px)',
          border: '1px solid #1E2D45',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)'
        }}
      >
        {/* Logo */}
        <div
          className="flex items-center justify-center rounded-lg transition-all duration-200"
          style={{
            width: '40px',
            height: '40px',
            backgroundColor: '#7C5CFC',
            boxShadow: '0 0 16px rgba(124, 92, 252, 0.5)'
          }}
        >
          <Sparkles size={28} color="white" />
        </div>

        {/* Main Navigation Icons */}
        <div className="flex flex-col items-center gap-1.5 mt-1">
          {mainIcons.map(({ icon: Icon, id, isActive, onClick }) => (
            <button
              key={id}
              onClick={onClick}
              className="flex items-center justify-center rounded-lg transition-all duration-200"
              style={{
                width: '36px',
                height: '36px',
                backgroundColor: isActive ? 'rgba(124, 92, 252, 0.12)' : 'transparent',
                color: isActive ? '#7C5CFC' : '#94A3B8',
                boxShadow: isActive ? '0 0 16px rgba(124, 92, 252, 0.3)' : 'none'
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = '#1C2840';
                  e.currentTarget.style.color = '#F1F5F9';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = 'transparent';
                  e.currentTarget.style.color = '#94A3B8';
                }
              }}
            >
              <Icon size={20} />
            </button>
          ))}
        </div>

        {/* Divider */}
        <div
          className="my-1"
          style={{
            width: '20px',
            height: '1px',
            backgroundColor: '#1E2D45'
          }}
        />

        {/* Group Trigger Icon */}
        <button
          ref={triggerRef}
          onClick={() => setIsGroupOpen(!isGroupOpen)}
          className="relative flex items-center justify-center rounded-lg transition-all duration-200"
          style={{
            width: '36px',
            height: '36px',
            backgroundColor:
              groupTriggerState === 'expanded'
                ? 'rgba(124, 92, 252, 0.12)'
                : groupTriggerState === 'sub-active'
                ? 'rgba(124, 92, 252, 0.08)'
                : 'transparent',
            color:
              groupTriggerState === 'expanded' || groupTriggerState === 'sub-active'
                ? '#7C5CFC'
                : '#94A3B8',
            boxShadow: groupTriggerState === 'expanded' ? '0 0 16px rgba(124, 92, 252, 0.3)' : 'none'
          }}
          onMouseEnter={(e) => {
            if (groupTriggerState === 'collapsed') {
              e.currentTarget.style.backgroundColor = '#1C2840';
              e.currentTarget.style.color = '#F1F5F9';
            }
          }}
          onMouseLeave={(e) => {
            if (groupTriggerState === 'collapsed') {
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.color = '#94A3B8';
            }
          }}
        >
          <LayoutGrid size={20} />
          {/* Indicator dot for sub-page active */}
          {groupTriggerState === 'expanded' && (
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
          )}
        </button>

        {/* Spacer */}
        <div className="flex-grow min-h-[20px]" />

        {/* User Avatar */}
        <div className="relative">
          <div
            className="flex items-center justify-center rounded-full"
            style={{
              width: '36px',
              height: '36px',
              backgroundColor: '#7C5CFC',
              fontSize: '13px',
              fontWeight: 600,
              color: 'white'
            }}
          >
            {userInitials}
          </div>
          {/* Presence dot */}
          {userOnline && (
            <div
              className="absolute bottom-0 right-0 rounded-full"
              style={{
                width: '10px',
                height: '10px',
                backgroundColor: '#22C55E',
                border: '2px solid rgba(15, 24, 41, 0.7)'
              }}
            />
          )}
        </div>
      </div>

      {/* Group Flyout Panel */}
      {isGroupOpen && (
        <div
          ref={panelRef}
          className="absolute left-[70px] flex flex-col"
          style={{
            width: '220px',
            backgroundColor: 'rgba(15, 24, 41, 0.92)',
            backdropFilter: 'blur(24px)',
            border: '1px solid #1E2D45',
            borderRadius: '16px',
            boxShadow:
              '0 8px 40px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(124, 92, 252, 0.08)',
            padding: '8px',
            animation: 'slideInFromLeft 200ms ease-out',
            zIndex: 100
          }}
        >
          {/* Arrow/Pointer */}
          <div
            className="absolute"
            style={{
              left: '-5px',
              top: '50%',
              transform: 'translateY(-50%) rotate(45deg)',
              width: '8px',
              height: '8px',
              backgroundColor: 'rgba(15, 24, 41, 0.92)',
              borderLeft: '1px solid #1E2D45',
              borderBottom: '1px solid #1E2D45'
            }}
          />

          {/* Panel Header */}
          <div
            className="flex items-center justify-between px-2 mb-1"
            style={{
              height: '32px'
            }}
          >
            <div
              style={{
                fontSize: '11px',
                fontWeight: 600,
                color: '#475569',
                textTransform: 'uppercase',
                letterSpacing: '0.08em'
              }}
            >
              More Modules
            </div>
            <button
              onClick={() => setIsGroupOpen(false)}
              className="flex items-center justify-center transition-colors duration-200"
              style={{
                width: '20px',
                height: '20px',
                color: '#475569'
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#F1F5F9')}
              onMouseLeave={(e) => (e.currentTarget.style.color = '#475569')}
            >
              <X size={12} />
            </button>
          </div>

          {/* Divider */}
          <div
            style={{
              height: '1px',
              backgroundColor: '#1E2D45',
              marginBottom: '4px'
            }}
          />

          {/* Group Items */}
          <div className="flex flex-col gap-0.5">
            {groupItems.map((item) => {
              const isActive = item.id === activeGroupItemId;
              const isHovered = item.id === hoveredGroupItem;
              const ItemIcon = item.icon;

              return (
                <button
                  key={item.id}
                  onClick={() => {
                    onGroupItemClick?.(item.id);
                    setIsGroupOpen(false);
                  }}
                  onMouseEnter={() => setHoveredGroupItem(item.id)}
                  onMouseLeave={() => setHoveredGroupItem(null)}
                  className="relative flex items-center gap-2.5 px-3 rounded-[10px] transition-all duration-150"
                  style={{
                    height: '40px',
                    backgroundColor: isActive
                      ? 'rgba(124, 92, 252, 0.12)'
                      : isHovered
                      ? '#1C2840'
                      : 'transparent'
                  }}
                >
                  {/* Left accent bar */}
                  {isActive && (
                    <div
                      className="absolute left-0 rounded-r"
                      style={{
                        width: '3px',
                        height: '20px',
                        backgroundColor: '#7C5CFC',
                        borderRadius: '0 2px 2px 0'
                      }}
                    />
                  )}

                  <ItemIcon
                    size={18}
                    style={{
                      color: isActive ? '#7C5CFC' : isHovered ? '#F1F5F9' : '#94A3B8'
                    }}
                  />
                  <div
                    style={{
                      fontSize: '13px',
                      fontWeight: isActive ? 600 : 500,
                      color: isActive ? '#7C5CFC' : isHovered ? '#F1F5F9' : '#94A3B8'
                    }}
                  >
                    {item.label}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Animation Keyframes */}
      <style>{`
        @keyframes slideInFromLeft {
          from {
            opacity: 0;
            transform: translateX(-8px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
      `}</style>
    </div>
  );
}
