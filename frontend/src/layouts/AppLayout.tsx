import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { IconRail } from '@/components/layout/IconRail'
import { ThreadPanel } from '@/components/layout/ThreadPanel'
import { ChatProvider } from '@/contexts/ChatContext'
import { useChatState } from '@/hooks/useChatState'

export function AppLayout() {
  const location = useLocation()
  const chatState = useChatState()
  const showThreadPanel = location.pathname === '/'
  const [panelCollapsed, setPanelCollapsed] = useState(false)

  return (
    <ChatProvider value={chatState}>
      <div className="flex h-screen bg-background mesh-bg overflow-hidden">
        <IconRail />
        {showThreadPanel && (
          <ThreadPanel
            collapsed={panelCollapsed}
            onToggleCollapse={() => setPanelCollapsed((prev) => !prev)}
          />
        )}
        <main className="relative z-10 flex flex-1 flex-col overflow-hidden">
          <Outlet />
        </main>
      </div>
    </ChatProvider>
  )
}
