export type AnalysisDepth = 'quick' | 'standard' | 'deep';

interface AnalysisDepthControlProps {
  value: AnalysisDepth;
  onChange?: (value: AnalysisDepth) => void;
  size?: 'sm' | 'md' | 'lg';
}

export function AnalysisDepthControl({ value, onChange, size = 'md' }: AnalysisDepthControlProps) {
  const options: { value: AnalysisDepth; label: string }[] = [
    { value: 'quick', label: 'Quick' },
    { value: 'standard', label: 'Standard' },
    { value: 'deep', label: 'Deep' }
  ];

  const sizeConfig = {
    sm: {
      height: '32px',
      padding: '3px',
      fontSize: '11px',
      gap: '2px'
    },
    md: {
      height: '40px',
      padding: '4px',
      fontSize: '13px',
      gap: '3px'
    },
    lg: {
      height: '48px',
      padding: '5px',
      fontSize: '14px',
      gap: '4px'
    }
  };

  const sizes = sizeConfig[size];

  return (
    <div
      className="flex items-center rounded-xl"
      style={{
        height: sizes.height,
        padding: sizes.padding,
        backgroundColor: '#162033',
        border: '1px solid #1E2D45',
        gap: sizes.gap,
        width: 'fit-content'
      }}
    >
      {options.map((option) => {
        const isActive = value === option.value;
        return (
          <button
            key={option.value}
            onClick={() => onChange?.(option.value)}
            className="flex items-center justify-center rounded-[10px] transition-all duration-200"
            style={{
              minWidth: size === 'sm' ? '64px' : size === 'md' ? '80px' : '96px',
              height: '100%',
              backgroundColor: isActive ? '#0F1829' : 'transparent',
              fontSize: sizes.fontSize,
              fontWeight: 600,
              color: isActive ? '#F1F5F9' : '#475569',
              boxShadow: isActive ? '0 1px 4px rgba(0, 0, 0, 0.3)' : 'none',
              cursor: 'pointer'
            }}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
