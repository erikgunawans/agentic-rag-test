import { MessageSquare, Search, Upload, FileSearch } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface QuickActionGridProps {
  onActionClick?: (actionId: string) => void
}

interface ActionCard {
  id: string
  icon: LucideIcon
  color: string
  hoverBorder: string
  hoverShadow: string
  title: string
  subtitle: string
}

const actions: [ActionCard, ActionCard, ActionCard, ActionCard] = [
  {
    id: 'document-qa',
    icon: MessageSquare,
    color: '#7C5CFC',
    hoverBorder: 'rgba(124,92,252,0.4)',
    hoverShadow: 'rgba(124,92,252,0.15)',
    title: 'Document Q&A',
    subtitle: 'Ask questions about your files',
  },
  {
    id: 'search-documents',
    icon: Search,
    color: '#22D3EE',
    hoverBorder: 'rgba(34,211,238,0.4)',
    hoverShadow: 'rgba(34,211,238,0.15)',
    title: 'Search Documents',
    subtitle: 'Find specific content across all docs',
  },
  {
    id: 'upload-process',
    icon: Upload,
    color: '#34D399',
    hoverBorder: 'rgba(52,211,153,0.4)',
    hoverShadow: 'rgba(52,211,153,0.15)',
    title: 'Upload & Process',
    subtitle: 'Add new documents to your knowledge base',
  },
  {
    id: 'analyze-content',
    icon: FileSearch,
    color: '#F59E0B',
    hoverBorder: 'rgba(245,158,11,0.4)',
    hoverShadow: 'rgba(245,158,11,0.15)',
    title: 'Analyze Content',
    subtitle: 'Get insights and summaries from docs',
  },
]

function ActionCardItem({
  action,
  className,
  onClick,
}: {
  action: ActionCard
  className?: string
  onClick?: () => void
}) {
  const Icon = action.icon

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'group bg-bg-elevated rounded-2xl border border-border-subtle',
        'flex items-center gap-3 px-5 cursor-pointer transition-all duration-200',
        className
      )}
      style={
        {
          '--action-hover-border': action.hoverBorder,
          '--action-hover-shadow': action.hoverShadow,
        } as React.CSSProperties
      }
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = action.hoverBorder
        e.currentTarget.style.boxShadow = `0 4px 20px ${action.hoverShadow}`
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = ''
        e.currentTarget.style.boxShadow = ''
      }}
    >
      <Icon size={22} style={{ color: action.color }} className="shrink-0" />
      <div className="flex flex-col items-start">
        <span className="text-sm font-semibold text-foreground">{action.title}</span>
        <span className="text-xs text-text-faint">{action.subtitle}</span>
      </div>
    </button>
  )
}

export function QuickActionGrid({ onActionClick }: QuickActionGridProps) {
  return (
    <div className="w-full max-w-[820px] mt-5 flex flex-col gap-3">
      {/* Row 1 */}
      <div className="flex gap-3 h-[72px]">
        <ActionCardItem
          action={actions[0]}
          className="w-[340px] shrink-0"
          onClick={() => onActionClick?.(actions[0].id)}
        />
        <ActionCardItem
          action={actions[1]}
          className="flex-1 min-w-0"
          onClick={() => onActionClick?.(actions[1].id)}
        />
      </div>
      {/* Row 2 */}
      <div className="flex gap-3 h-[72px]">
        <ActionCardItem
          action={actions[2]}
          className="flex-1 min-w-0"
          onClick={() => onActionClick?.(actions[2].id)}
        />
        <ActionCardItem
          action={actions[3]}
          className="w-[340px] shrink-0"
          onClick={() => onActionClick?.(actions[3].id)}
        />
      </div>
    </div>
  )
}
