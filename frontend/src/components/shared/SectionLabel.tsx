interface SectionLabelProps {
  label: string
  description?: string
}

export function SectionLabel({ label, description }: SectionLabelProps) {
  return (
    <div className="space-y-0.5">
      <label className="text-sm font-medium text-foreground">{label}</label>
      {description && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
    </div>
  )
}
