interface HintChip {
  color: string;
  label: string;
}

interface HintChipRowProps {
  chips: [HintChip, HintChip, HintChip];
}

export function HintChipRow({ chips }: HintChipRowProps) {
  return (
    <div className="flex items-center gap-2">
      {chips.map((chip, index) => (
        <div
          key={index}
          className="flex items-center gap-1.5"
          style={{
            height: '26px',
            padding: '0 10px',
            borderRadius: '20px',
            backgroundColor: '#162033',
            border: '1px solid #1E2D45',
            fontSize: '11px',
            color: '#475569'
          }}
        >
          <div
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: chip.color
            }}
          />
          {chip.label}
        </div>
      ))}
    </div>
  );
}
