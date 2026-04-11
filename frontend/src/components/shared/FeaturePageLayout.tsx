import { HistorySection, type HistoryItem } from './HistorySection'

interface FeaturePageLayoutProps {
  children: React.ReactNode
  historyTitle: string
  historyItems: HistoryItem[]
}

export function FeaturePageLayout({ children, historyTitle, historyItems }: FeaturePageLayoutProps) {
  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-[676px] space-y-6">
          {children}
        </div>
      </div>
      <div className="hidden lg:flex w-[223px] shrink-0 flex-col border-l border-border/50 glass">
        <HistorySection title={historyTitle} items={historyItems} />
      </div>
    </div>
  )
}
