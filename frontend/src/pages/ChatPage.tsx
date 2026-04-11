import { useChatContext } from '@/contexts/ChatContext'
import { MessageView } from '@/components/chat/MessageView'
import { MessageInput } from '@/components/chat/MessageInput'
import { WelcomeScreen } from '@/components/chat/WelcomeScreen'

export function ChatPage() {
  const {
    activeThreadId,
    messages,
    isStreaming,
    streamingContent,
    activeTools,
    toolResults,
    activeAgent,
    handleSendMessage,
  } = useChatContext()

  if (!activeThreadId) {
    return <WelcomeScreen />
  }

  return (
    <>
      <MessageView
        messages={messages}
        streamingContent={streamingContent}
        isStreaming={isStreaming}
        activeTools={activeTools}
        toolResults={toolResults}
        activeAgent={activeAgent}
      />
      <MessageInput onSend={handleSendMessage} disabled={isStreaming} />
    </>
  )
}
