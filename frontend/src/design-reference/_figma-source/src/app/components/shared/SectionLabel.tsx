interface SectionLabelProps {
  children: React.ReactNode;
  required?: boolean;
}

export function SectionLabel({ children, required = false }: SectionLabelProps) {
  return (
    <div className="flex items-center gap-2 mb-2">
      <div
        style={{
          fontSize: '11px',
          fontWeight: 600,
          color: '#475569',
          textTransform: 'uppercase',
          letterSpacing: '0.08em'
        }}
      >
        {children}
      </div>
      {required && (
        <div style={{ fontSize: '11px', color: '#475569', marginLeft: 'auto' }}>
          (Required)
        </div>
      )}
    </div>
  );
}
