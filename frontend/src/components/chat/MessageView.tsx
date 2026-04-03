import { useEffect, useRef } from 'react'
import { StreamingMessage } from './StreamingMessage'
import { ToolCallCard, ToolCallList } from './ToolCallCard'
import type { Message, ToolStartEvent, ToolResultEvent } from '@/lib/database.types'

interface MessageViewProps {
  messages: Message[]
  streamingContent: string
  isStreaming: boolean
  activeTools?: ToolStartEvent[]
  toolResults?: ToolResultEvent[]
}

export function MessageView({
  messages,
  streamingContent,
  isStreaming,
  activeTools = [],
  toolResults = [],
}: MessageViewProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent, activeTools, toolResults])

  if (messages.length === 0 && !isStreaming) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm text-muted-foreground">Send a message to start the conversation</p>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col gap-4 p-4 overflow-y-auto">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div className={`max-w-[75%] ${msg.role === 'user' ? '' : 'space-y-1'}`}>
            {msg.role === 'assistant' && msg.tool_calls?.calls && msg.tool_calls.calls.length > 0 && (
              <ToolCallList toolCalls={msg.tool_calls.calls} />
            )}
            <div
              className={`rounded-lg px-4 py-2 text-sm ${
                msg.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-foreground'
              }`}
            >
              <div className="whitespace-pre-wrap break-words">{msg.content}</div>
            </div>
          </div>
        </div>
      ))}

      {isStreaming && (
        <div className="flex justify-start">
          <div className="max-w-[75%] space-y-1">
            {/* Completed tool results */}
            {toolResults.map((tr, i) => (
              <ToolCallCard
                key={`result-${i}`}
                tool={tr.tool}
                input={{}}
                output={tr.output}
              />
            ))}

            {/* Currently running tools */}
            {activeTools.map((at, i) => (
              <ToolCallCard
                key={`active-${i}`}
                tool={at.tool}
                input={at.input}
                isLoading={true}
              />
            ))}

            {/* Streaming text response */}
            {streamingContent && (
              <div className="rounded-lg px-4 py-2 bg-muted text-foreground">
                <StreamingMessage content={streamingContent} isStreaming={true} />
              </div>
            )}

            {/* Show loading state when no content yet and no active tools */}
            {!streamingContent && activeTools.length === 0 && toolResults.length === 0 && (
              <div className="rounded-lg px-4 py-2 bg-muted text-foreground">
                <StreamingMessage content="" isStreaming={true} />
              </div>
            )}
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
