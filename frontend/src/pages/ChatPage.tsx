import { useChatContext } from '@/contexts/ChatContext'
import { MessageView } from '@/components/chat/MessageView'
import { MessageInput } from '@/components/chat/MessageInput'
import { WelcomeScreen } from '@/components/chat/WelcomeScreen'

export function ChatPage() {
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
    handleSendMessage,
    handleSwitchBranch,
    handleForkAt,
    handleCancelFork,
  } = useChatContext()

  if (!activeThreadId) {
    return <WelcomeScreen />
  }

  return (
    <div className="flex flex-1 min-h-0 flex-col">
      <MessageView
        messages={messages}
        allMessages={allMessages}
        streamingContent={streamingContent}
        isStreaming={isStreaming}
        activeTools={activeTools}
        toolResults={toolResults}
        activeAgent={activeAgent}
        redactionStage={redactionStage}
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
  )
}
