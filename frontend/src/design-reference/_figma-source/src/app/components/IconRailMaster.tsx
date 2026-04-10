import { LucideIcon, Sparkles } from 'lucide-react';

export interface IconSlot {
  Icon: LucideIcon;
  id: number;
  label?: string;
}

interface IconRailMasterProps {
  slots: IconSlot[];
  activeSlotId: number;
  onSlotClick?: (id: number) => void;
  showLabels?: boolean;
  size?: 'compact' | 'floating';
}

export function IconRailMaster({ 
  slots, 
  activeSlotId, 
  onSlotClick,
  showLabels = false,
  size = 'floating'
}: IconRailMasterProps) {
  const isCompact = size === 'compact';

  return (
    <div 
      className="relative flex items-center justify-center" 
      style={{ 
        width: isCompact ? '60px' : '88px',
        backgroundColor: isCompact ? '#080C14' : '#0B1120',
        height: '100%'
      }}
    >
      {isCompact ? (
        // Compact version - no floating pill
        <div className="flex flex-col items-center gap-2 py-4 w-full">
          {/* Logo */}
          <div 
            className="flex items-center justify-center rounded-lg transition-all duration-200 mb-2"
            style={{
              width: '40px',
              height: '40px',
              backgroundColor: '#7C5CFC',
              boxShadow: '0 0 16px rgba(124, 92, 252, 0.5)'
            }}
          >
            <Sparkles size={24} color="white" />
          </div>

          {/* Divider */}
          <div 
            className="mb-1"
            style={{
              width: '24px',
              height: '1px',
              backgroundColor: '#1E2D45'
            }}
          />

          {/* Icon Slots */}
          <div className="flex flex-col items-center gap-2">
            {slots.map(({ Icon, id, label }) => {
              const isActive = activeSlotId === id;
              return (
                <button
                  key={id}
                  onClick={() => onSlotClick?.(id)}
                  className="flex items-center justify-center rounded-lg transition-all duration-200 relative group"
                  style={{
                    width: '36px',
                    height: '36px',
                    backgroundColor: isActive ? 'rgba(124, 92, 252, 0.12)' : 'transparent',
                    color: isActive ? '#7C5CFC' : '#94A3B8',
                    boxShadow: isActive ? '0 0 16px rgba(124, 92, 252, 0.3)' : 'none'
                  }}
                >
                  <Icon size={20} />
                  {showLabels && label && (
                    <div
                      className="absolute left-full ml-3 px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none"
                      style={{
                        backgroundColor: '#0F1829',
                        border: '1px solid #1E2D45',
                        fontSize: '11px',
                        color: '#F1F5F9',
                        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.4)'
                      }}
                    >
                      {label}
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {/* Spacer */}
          <div className="flex-grow min-h-[20px]" />

          {/* Avatar */}
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
              AS
            </div>
            {/* Presence dot */}
            <div 
              className="absolute bottom-0 right-0 rounded-full"
              style={{
                width: '10px',
                height: '10px',
                backgroundColor: '#22C55E',
                border: '2px solid #080C14'
              }}
            />
          </div>
        </div>
      ) : (
        // Floating pill version
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

          {/* Divider */}
          <div 
            className="my-1"
            style={{
              width: '24px',
              height: '1px',
              backgroundColor: '#1E2D45'
            }}
          />

          {/* Icon Slots */}
          <div className="flex flex-col items-center gap-1.5">
            {slots.map(({ Icon, id, label }) => {
              const isActive = activeSlotId === id;
              return (
                <button
                  key={id}
                  onClick={() => onSlotClick?.(id)}
                  className="flex items-center justify-center rounded-lg transition-all duration-200 relative group"
                  style={{
                    width: '36px',
                    height: '36px',
                    backgroundColor: isActive ? 'rgba(124, 92, 252, 0.12)' : 'transparent',
                    color: isActive ? '#7C5CFC' : '#94A3B8',
                    boxShadow: isActive ? '0 0 16px rgba(124, 92, 252, 0.3)' : 'none'
                  }}
                >
                  <Icon size={20} />
                  {showLabels && label && (
                    <div
                      className="absolute left-full ml-3 px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none"
                      style={{
                        backgroundColor: '#0F1829',
                        border: '1px solid #1E2D45',
                        fontSize: '11px',
                        color: '#F1F5F9',
                        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.4)'
                      }}
                    >
                      {label}
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {/* Spacer */}
          <div className="flex-grow min-h-[20px]" />

          {/* Avatar */}
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
              AS
            </div>
            {/* Presence dot */}
            <div 
              className="absolute bottom-0 right-0 rounded-full"
              style={{
                width: '10px',
                height: '10px',
                backgroundColor: '#22C55E',
                border: '2px solid #080C14'
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
