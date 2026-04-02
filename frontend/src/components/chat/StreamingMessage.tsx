interface StreamingMessageProps {
  content: string
  isStreaming: boolean
}

export function StreamingMessage({ content, isStreaming }: StreamingMessageProps) {
  return (
    <div className="whitespace-pre-wrap break-words text-sm">
      {content}
      {isStreaming && (
        <span className="inline-block w-0.5 h-4 bg-foreground ml-0.5 animate-pulse" />
      )}
    </div>
  )
}
