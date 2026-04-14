import { Search, GitCompare, ShieldCheck, FilePlus } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'

const chips = [
  { key: 'chip.searchDoc', icon: Search },
  { key: 'chip.compareDoc', icon: GitCompare },
  { key: 'chip.validateDoc', icon: ShieldCheck },
  { key: 'chip.createDoc', icon: FilePlus },
] as const

interface SuggestionChipsProps {
  onSelect?: (text: string) => void
}

export function SuggestionChips({ onSelect }: SuggestionChipsProps) {
  const { t } = useI18n()

  return (
    <div className="flex flex-wrap justify-center gap-2">
      {chips.map(({ key, icon: Icon }) => (
        <button
          key={key}
          type="button"
          onClick={() => onSelect?.(t(key))}
          className="flex items-center gap-2 rounded-full border border-border px-4 py-2 text-xs text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors cursor-pointer"
        >
          <Icon className="h-3.5 w-3.5" />
          {t(key)}
        </button>
      ))}
    </div>
  )
}
