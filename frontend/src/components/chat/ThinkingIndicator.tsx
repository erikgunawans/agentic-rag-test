export function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-2 py-1">
      <div className="flex items-center gap-1">
        <span
          className="h-2 w-2 rounded-full bg-primary animate-bounce"
          style={{ animationDelay: '0ms', animationDuration: '600ms' }}
        />
        <span
          className="h-2 w-2 rounded-full bg-primary animate-bounce"
          style={{ animationDelay: '150ms', animationDuration: '600ms' }}
        />
        <span
          className="h-2 w-2 rounded-full bg-primary animate-bounce"
          style={{ animationDelay: '300ms', animationDuration: '600ms' }}
        />
      </div>
      <span className="text-xs text-muted-foreground">Thinking...</span>
    </div>
  )
}
