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
        className="group flex items-start gap-2.5 rounded-xl border border-border/50 bg-card p-4 text-left transition-all duration-200 hover:bg-accent/50 hover:shadow-[var(--shadow-md)] cursor-pointer animate-fade-in-up interactive-lift focus-ring"
        style={{
          animationDelay: `${index * 100}ms`,
        }}
      >
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <Icon className="h-4 w-4 shrink-0" style={{ color: colorVar }} />
            <p className="text-sm font-medium text-foreground">{t(titleKey)}</p>
          </div>
          <p className="text-xs text-muted-foreground mt-1 pl-6">{t(descKey)}</p>
        </div>
        <span className="text-muted-foreground/30 group-hover:text-muted-foreground/60 transition-colors text-xs mt-0.5">&rarr;</span>
      </button>
    )
  }

  return (
    <div className="flex flex-col gap-3 w-full stagger-children">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {cards.slice(0, 2).map((card, i) => renderCard(card, i))}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-[3fr_2fr] gap-3">
        {cards.slice(2, 4).map((card, i) => renderCard(card, i + 2))}
      </div>
    </div>
  )
}
