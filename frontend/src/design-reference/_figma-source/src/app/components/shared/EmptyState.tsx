import { LucideIcon } from 'lucide-react';
import { HintChipRow } from './HintChipRow';

interface EmptyStateProps {
  icon: LucideIcon;
  line1: string;
  line2: string;
  hintChips: [
    { color: string; label: string },
    { color: string; label: string },
    { color: string; label: string }
  ];
}

export function EmptyState({ icon: Icon, line1, line2, hintChips }: EmptyStateProps) {
  return (
    <div
      className="flex-1 flex items-center justify-center relative overflow-hidden"
      style={{ backgroundColor: '#0B1120' }}
    >
      {/* Mesh Gradients */}
      <div
        className="absolute top-0 right-0 pointer-events-none"
        style={{
          width: '600px',
          height: '600px',
          background: 'radial-gradient(circle, rgba(76, 29, 149, 0.06) 0%, transparent 70%)'
        }}
      />
      <div
        className="absolute bottom-0 left-0 pointer-events-none"
        style={{
          width: '500px',
          height: '500px',
          background: 'radial-gradient(circle, rgba(10, 31, 61, 0.3) 0%, transparent 70%)'
        }}
      />

      {/* Empty State Content */}
      <div className="flex flex-col items-center gap-4 relative z-10">
        {/* Nested circles */}
        <div
          className="flex items-center justify-center rounded-full"
          style={{
            width: '96px',
            height: '96px',
            backgroundColor: 'rgba(124, 92, 252, 0.06)',
            border: '1px solid rgba(124, 92, 252, 0.12)'
          }}
        >
          <div
            className="flex items-center justify-center rounded-full"
            style={{
              width: '72px',
              height: '72px',
              backgroundColor: 'rgba(124, 92, 252, 0.10)',
              border: '1px solid rgba(124, 92, 252, 0.18)'
            }}
          >
            <Icon size={32} style={{ color: 'rgba(124, 92, 252, 0.5)' }} />
          </div>
        </div>

        {/* Body text - 2 lines */}
        <div className="flex flex-col items-center gap-1">
          <div
            style={{
              fontSize: '14px',
              color: '#475569',
              textAlign: 'center',
              maxWidth: '340px',
              lineHeight: 1.6
            }}
          >
            {line1}
          </div>
          <div
            style={{
              fontSize: '14px',
              color: '#475569',
              textAlign: 'center',
              maxWidth: '340px',
              lineHeight: 1.6
            }}
          >
            {line2}
          </div>
        </div>

        {/* Hint chips */}
        <HintChipRow chips={hintChips} />
      </div>
    </div>
  );
}
