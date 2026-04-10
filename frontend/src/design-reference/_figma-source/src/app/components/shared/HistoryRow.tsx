import { useState, ReactNode } from 'react';
import { ChevronRight } from 'lucide-react';

interface HistoryRowProps {
  id: number | string;
  badge: ReactNode;
  name: string;
  metaChip: string;
  timestamp: string;
  statusIcon?: ReactNode;
  onClick?: () => void;
}

export function HistoryRow({
  id,
  badge,
  name,
  metaChip,
  timestamp,
  statusIcon,
  onClick
}: HistoryRowProps) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <button
      className="w-full flex items-center gap-2.5 px-4 transition-colors duration-150"
      style={{
        height: '44px',
        backgroundColor: isHovered ? '#1C2840' : 'transparent',
        cursor: 'pointer'
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={onClick}
    >
      {/* Badge */}
      {badge}

      {/* Center info */}
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
          {name}
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
            {metaChip}
          </div>
          <div
            style={{
              width: '3px',
              height: '3px',
              borderRadius: '50%',
              backgroundColor: '#475569'
            }}
          />
          <div style={{ fontSize: '10px', color: '#475569' }}>{timestamp}</div>
        </div>
      </div>

      {/* Right: status icon or chevron on hover */}
      <div style={{ flexShrink: 0 }}>
        {isHovered ? (
          <ChevronRight size={14} style={{ color: '#475569' }} />
        ) : (
          statusIcon
        )}
      </div>
    </button>
  );
}
