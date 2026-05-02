import { useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useChatContext } from '@/contexts/ChatContext'
import { MessageView } from '@/components/chat/MessageView'
import { MessageInput } from '@/components/chat/MessageInput'
import { WelcomeScreen } from '@/components/chat/WelcomeScreen'
import { PlanPanel } from '@/components/chat/PlanPanel'

export function ChatPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const consumedRef = useRef(false)

  const {
    activeThreadId,
    messages,
    allMessages,
    forkParentId,
    isStreaming,
    streamingContent,
    activeTools,
    toolResults,
    activeAgent,
    redactionStage,
    sandboxStreams,
    handleSendMessage,
    handleSendFirstMessage,
    handleSwitchBranch,
    handleForkAt,
    handleCancelFork,
  } = useChatContext()

  // Consume location.state.prefill exactly once. Sources: SkillsPage "Create with AI" or "Try in Chat" buttons.
  // Re-runs when activeThreadId changes so we don't discard prefill before the thread is ready.
  useEffect(() => {
    const stateObj = location.state as { prefill?: string } | null
    const prefill = stateObj?.prefill
    if (prefill && !consumedRef.current) {
      consumedRef.current = true
      if (activeThreadId) {
        handleSendMessage(prefill)
      } else {
        handleSendFirstMessage(prefill)
      }
      // Clear the state so refresh / back-nav doesn't re-trigger.
      navigate(location.pathname, { replace: true, state: null })
    }
  }, [location.state, location.pathname, activeThreadId, handleSendMessage, handleSendFirstMessage, navigate])

  if (!activeThreadId) {
    return <WelcomeScreen />
  }

  return (
    // Phase 17 / D-20: Plan Panel slots into the chat layout as a right-side
    // persistent sidebar (coexists with message view + input).
    // flex-row so PlanPanel and the chat column sit side-by-side.
    <div className="flex flex-1 min-h-0 flex-row">
      {/* Main chat column */}
      <div className="flex flex-1 min-h-0 flex-col min-w-0">
        <MessageView
          messages={messages}
          allMessages={allMessages}
          streamingContent={streamingContent}
          isStreaming={isStreaming}
          activeTools={activeTools}
          toolResults={toolResults}
          activeAgent={activeAgent}
          redactionStage={redactionStage}
          sandboxStreams={sandboxStreams}
          onFork={handleForkAt}
          onSwitchBranch={handleSwitchBranch}
        />
        <MessageInput
          onSend={handleSendMessage}
          disabled={isStreaming}
          forkParentId={forkParentId}
          onCancelFork={handleCancelFork}
        />
      </div>
      {/* Phase 17 Plan Panel — visible when deep mode active or thread has todos (D-22) */}
      <PlanPanel />
    </div>
  )
}
