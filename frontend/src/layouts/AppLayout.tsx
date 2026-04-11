import { Outlet, useLocation } from 'react-router-dom'
import { IconRail } from '@/components/layout/IconRail'
import { ThreadPanel } from '@/components/layout/ThreadPanel'
import { ChatProvider } from '@/contexts/ChatContext'
import { useChatState } from '@/hooks/useChatState'

export function AppLayout() {
  const location = useLocation()
  const chatState = useChatState()
  const showThreadPanel = location.pathname === '/'

  return (
    <ChatProvider value={chatState}>
      <div className="flex h-screen bg-background">
        <IconRail />
        {showThreadPanel && <ThreadPanel />}
        <main className="flex flex-1 flex-col overflow-hidden">
          <Outlet />
        </main>
      </div>
    </ChatProvider>
  )
}
