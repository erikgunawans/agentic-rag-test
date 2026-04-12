import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { IconRail } from '@/components/layout/IconRail'
import { ThreadPanel } from '@/components/layout/ThreadPanel'
import { ChatProvider } from '@/contexts/ChatContext'
import { useChatState } from '@/hooks/useChatState'

export function AppLayout() {
  const location = useLocation()
  const chatState = useChatState()
  const showThreadPanel = location.pathname === '/'
  const [panelCollapsed, setPanelCollapsed] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <ChatProvider value={chatState}>
      <div className="flex h-screen bg-background mesh-bg overflow-hidden">
        {/* Desktop icon rail — hidden on mobile */}
        <div className="hidden md:flex">
          <IconRail />
        </div>

        {/* Mobile top header bar — visible only on mobile */}
        <div className="md:hidden fixed top-0 inset-x-0 z-30 flex items-center justify-between px-4 h-14 bg-background/95 backdrop-blur-md border-b border-border/50">
          <span className="text-sm font-bold text-foreground">Knowledge Hub</span>
          {showThreadPanel && (
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="flex h-10 w-10 items-center justify-center rounded-lg hover:bg-accent transition-colors"
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          )}
        </div>

        {/* Mobile sidebar overlay — slides in from left */}
        {mobileMenuOpen && showThreadPanel && (
          <div className="md:hidden">
            <div className="mobile-backdrop" onClick={() => setMobileMenuOpen(false)} />
            <div className="mobile-panel bg-background border-r border-border/50">
              <ThreadPanel
                collapsed={false}
                onToggleCollapse={() => setMobileMenuOpen(false)}
              />
            </div>
          </div>
        )}

        {/* Desktop sidebar — hidden on mobile */}
        {showThreadPanel && (
          <div className="hidden md:flex">
            <ThreadPanel
              collapsed={panelCollapsed}
              onToggleCollapse={() => setPanelCollapsed((prev) => !prev)}
            />
          </div>
        )}

        {/* Main content — top padding on mobile for the header bar */}
        <main className="relative z-10 flex flex-1 flex-col overflow-hidden pt-14 md:pt-0">
          <Outlet />
        </main>
      </div>
    </ChatProvider>
  )
}
