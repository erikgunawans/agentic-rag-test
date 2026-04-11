import { useNavigate } from 'react-router-dom'
import { FilePlus, GitCompare, ShieldCheck, Scale } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import type { LucideIcon } from 'lucide-react'

interface CardDef {
  titleKey: string
  descKey: string
  icon: LucideIcon
  path: string
  colorVar: string
  borderColor: string
}

const cards: CardDef[] = [
  {
    titleKey: 'card.create.title',
    descKey: 'card.create.desc',
    icon: FilePlus,
    path: '/create',
    colorVar: 'var(--feature-creation)',
    borderColor: 'border-[var(--feature-creation)]/30',
  },
  {
    titleKey: 'card.compare.title',
    descKey: 'card.compare.desc',
    icon: GitCompare,
    path: '/compare',
    colorVar: 'var(--feature-management)',
    borderColor: 'border-[var(--feature-management)]/30',
  },
  {
    titleKey: 'card.compliance.title',
    descKey: 'card.compliance.desc',
    icon: ShieldCheck,
    path: '/compliance',
    colorVar: 'var(--feature-compliance)',
    borderColor: 'border-[var(--feature-compliance)]/30',
  },
  {
    titleKey: 'card.analysis.title',
    descKey: 'card.analysis.desc',
    icon: Scale,
    path: '/analysis',
    colorVar: 'var(--feature-analysis)',
    borderColor: 'border-[var(--feature-analysis)]/30',
  },
]

export function SuggestionCards() {
  const { t } = useI18n()
  const navigate = useNavigate()

  return (
    <div className="grid grid-cols-2 gap-3 w-full">
      {cards.map(({ titleKey, descKey, icon: Icon, path, colorVar, borderColor }) => (
        <button
          key={path}
          onClick={() => navigate(path)}
          className={`flex items-center gap-3 rounded-xl border ${borderColor} bg-card p-4 text-left transition-colors hover:bg-accent/50 cursor-pointer`}
        >
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
            style={{ backgroundColor: `color-mix(in oklch, ${colorVar} 15%, transparent)`, color: colorVar }}
          >
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">{t(titleKey)}</p>
            <p className="text-xs text-muted-foreground">{t(descKey)}</p>
          </div>
        </button>
      ))}
    </div>
  )
}
