import { useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useChatContext } from '@/contexts/ChatContext'
import { MessageView } from '@/components/chat/MessageView'
import { MessageInput } from '@/components/chat/MessageInput'
import { WelcomeScreen } from '@/components/chat/WelcomeScreen'
import { PlanPanel } from '@/components/chat/PlanPanel'
import { WorkspacePanel } from '@/components/chat/WorkspacePanel'
import { AgentStatusChip } from '@/components/chat/AgentStatusChip'
import { TaskPanel } from '@/components/chat/TaskPanel'
import { HarnessBanner } from '@/components/chat/HarnessBanner'

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
    workspaceFiles, // Phase 18 / WS-07 / WS-11
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
        {/* Phase 20 / Plan 20-09 — HarnessBanner: full-width sticky band above chat scroll
            region. Renders above AgentStatusChip (z-20 > z-10). When harnessRun=null,
            the banner renders an sr-only stub (zero height) so AgentStatusChip isn't
            displaced. Placed in ChatPage (NOT AppLayout) per UI-SPEC L124 slot decision. */}
        <div className="sticky top-0 z-20 w-full">
          <HarnessBanner />
        </div>
        {/* Phase 19 / STATUS-01 / D-26: AgentStatusChip — sticky at top of chat column.
            Rendered here (NOT in AppLayout) — UI-SPEC L455 prohibits adding to AppLayout.
            Component is always mounted; internal visibility rule handles null state. */}
        <div className="sticky top-0 z-10 flex px-4 pt-2">
          <AgentStatusChip />
        </div>
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
      {/* Phase 18 Workspace Panel — visible whenever thread has workspace files (WS-11).
          Decoupled from Deep Mode — appears for any thread with files. */}
      <WorkspacePanel threadId={activeThreadId} files={workspaceFiles} />
      {/* Phase 19 Task Panel — rightmost panel; visible when tasks.size > 0 (D-25).
          Rendered here (NOT in AppLayout) — UI-SPEC L457. SubAgentPanel.tsx untouched. */}
      <TaskPanel />
    </div>
  )
}
