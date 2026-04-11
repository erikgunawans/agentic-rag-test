import { FileText } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useI18n } from '@/i18n/I18nContext'

export interface HistoryItem {
  id: string
  title: string
  subtitle: string
  time: string
}

interface HistorySectionProps {
  title: string
  items: HistoryItem[]
}

export function HistorySection({ title, items }: HistorySectionProps) {
  const { t } = useI18n()

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{title}</h3>
      </div>
      <ScrollArea className="flex-1">
        {items.length === 0 ? (
          <p className="p-4 text-xs text-muted-foreground text-center">{t('shared.history.empty')}</p>
        ) : (
          <div className="p-2 space-y-1">
            {items.map((item) => (
              <div
                key={item.id}
                className="flex items-start gap-2 rounded-md p-2 hover:bg-muted/50 transition-colors cursor-pointer"
              >
                <FileText className="h-4 w-4 shrink-0 mt-0.5 text-muted-foreground" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium truncate">{item.title}</p>
                  <p className="text-[10px] text-muted-foreground">{item.subtitle}</p>
                </div>
                <span className="text-[10px] text-muted-foreground shrink-0">{item.time}</span>
              </div>
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  )
}
