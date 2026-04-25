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
}

const cards: CardDef[] = [
  { titleKey: 'card.create.title', descKey: 'card.create.desc', icon: FilePlus, path: '/create', colorVar: 'var(--feature-creation)' },
  { titleKey: 'card.compare.title', descKey: 'card.compare.desc', icon: GitCompare, path: '/compare', colorVar: 'var(--feature-management)' },
  { titleKey: 'card.compliance.title', descKey: 'card.compliance.desc', icon: ShieldCheck, path: '/compliance', colorVar: 'var(--feature-compliance)' },
  { titleKey: 'card.analysis.title', descKey: 'card.analysis.desc', icon: Scale, path: '/analysis', colorVar: 'var(--feature-analysis)' },
]

export function SuggestionCards() {
  const { t } = useI18n()
  const navigate = useNavigate()

  function renderCard({ titleKey, descKey, icon: Icon, path, colorVar }: CardDef, index: number) {
    return (
      <button
        key={path}
        onClick={() => navigate(path)}
        className="group relative flex items-start gap-3 rounded-2xl border border-border/50 bg-card px-3.5 py-2.5 text-left cursor-pointer animate-fade-in-up overflow-hidden focus-ring card-luminous"
        style={{ animationDelay: `${index * 80}ms` }}
      >
        {/* Ambient colour wash on hover */}
        <div
          className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
          style={{ background: `radial-gradient(circle at 20% 60%, ${colorVar}18 0%, transparent 65%)` }}
        />

        {/* Icon with tinted background */}
        <div
          className="flex h-7 w-7 items-center justify-center rounded-lg shrink-0 relative z-10 transition-transform duration-300 group-hover:scale-110 mt-0.5"
          style={{ background: `color-mix(in oklch, ${colorVar} 12%, transparent)` }}
        >
          <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: colorVar }} />
        </div>

        <div className="flex-1 min-w-0 relative z-10">
          <p className="text-sm font-medium text-foreground leading-snug">{t(titleKey)}</p>
          <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed line-clamp-1">{t(descKey)}</p>
        </div>

        <span
          className="text-[11px] font-medium tracking-wide opacity-40 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all duration-200 relative z-10 mt-1 shrink-0"
          style={{ color: colorVar }}
        >
          →
        </span>
      </button>
    )
  }

  return (
    <div className="flex flex-col gap-2.5 w-full stagger-children">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {cards.slice(0, 2).map((card, i) => renderCard(card, i))}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-[3fr_2fr] gap-2.5">
        {cards.slice(2, 4).map((card, i) => renderCard(card, i + 2))}
      </div>
    </div>
  )
}
