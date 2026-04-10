import { useEffect, useRef } from 'react'
import { StreamingMessage } from './StreamingMessage'
import { ThinkingIndicator } from './ThinkingIndicator'
import { ToolCallCard, ToolCallList } from './ToolCallCard'
import { AgentBadge } from './AgentBadge'
import type { Message, ToolStartEvent, ToolResultEvent } from '@/lib/database.types'

interface MessageViewProps {
  messages: Message[]
  streamingContent: string
  isStreaming: boolean
  activeTools?: ToolStartEvent[]
  toolResults?: ToolResultEvent[]
  activeAgent?: { agent: string; display_name: string } | null
}

export function MessageView({
  messages,
  streamingContent,
  isStreaming,
  activeTools = [],
  toolResults = [],
  activeAgent = null,
}: MessageViewProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent, activeTools, toolResults, activeAgent])

  if (messages.length === 0 && !isStreaming) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-[15px] text-text-faint">Send a message to start the conversation</p>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col gap-4 p-4 overflow-y-auto scrollbar-kh">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div className={`max-w-[75%] ${msg.role === 'user' ? '' : 'space-y-1'}`}>
            {msg.role === 'assistant' && msg.tool_calls?.agent && (
              <AgentBadge agent={msg.tool_calls.agent} />
            )}
            {msg.role === 'assistant' && msg.tool_calls?.calls && msg.tool_calls.calls.length > 0 && (
              <ToolCallList toolCalls={msg.tool_calls.calls} />
            )}
            <div
              className={
                msg.role === 'user'
                  ? 'rounded-2xl px-4 py-3 text-[15px] bg-accent-primary text-white'
                  : 'rounded-2xl px-4 py-3 text-[15px] bg-bg-elevated text-foreground border border-border-subtle'
              }
            >
              <div className="whitespace-pre-wrap break-words">{msg.content}</div>
            </div>
          </div>
        </div>
      ))}

      {isStreaming && (
        <div className="flex justify-start">
          <div className="max-w-[75%] space-y-1">
            {activeAgent && (
              <AgentBadge agent={activeAgent.agent} displayName={activeAgent.display_name} active />
            )}

            {toolResults.map((tr, i) => (
              <ToolCallCard
                key={`result-${i}`}
                tool={tr.tool}
                input={{}}
                output={tr.output}
              />
            ))}

            {activeTools.map((at, i) => (
              <ToolCallCard
                key={`active-${i}`}
                tool={at.tool}
                input={at.input}
                isLoading={true}
              />
            ))}

            {streamingContent && (
              <div className="rounded-2xl px-4 py-3 bg-bg-elevated text-foreground border border-border-subtle">
                <StreamingMessage content={streamingContent} isStreaming={true} />
              </div>
            )}

            {!streamingContent && activeTools.length === 0 && toolResults.length === 0 && !activeAgent && (
              <div className="rounded-2xl px-4 py-3 bg-bg-elevated text-foreground border border-border-subtle">
                <ThinkingIndicator />
              </div>
            )}
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
