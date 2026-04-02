import { useEffect, useRef } from 'react'
import { StreamingMessage } from './StreamingMessage'
import type { Message } from '@/lib/database.types'

interface MessageViewProps {
  messages: Message[]
  streamingContent: string
  isStreaming: boolean
}

export function MessageView({ messages, streamingContent, isStreaming }: MessageViewProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

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
          <div
            className={`max-w-[75%] rounded-lg px-4 py-2 text-sm ${
              msg.role === 'user'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-foreground'
            }`}
          >
            <div className="whitespace-pre-wrap break-words">{msg.content}</div>
          </div>
        </div>
      ))}

      {isStreaming && (
        <div className="flex justify-start">
          <div className="max-w-[75%] rounded-lg px-4 py-2 bg-muted text-foreground">
            <StreamingMessage content={streamingContent} isStreaming={true} />
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
