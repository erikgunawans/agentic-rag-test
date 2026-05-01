import { useEffect, useMemo, useRef } from 'react'
import { GitFork, ChevronLeft, ChevronRight, ShieldAlert } from 'lucide-react'
import { StreamingMessage } from './StreamingMessage'
import { ThinkingIndicator } from './ThinkingIndicator'
import { ToolCallCard, ToolCallList } from './ToolCallCard'
import { AgentBadge } from './AgentBadge'
import { buildChildrenMap } from '@/lib/messageTree'
import { useI18n } from '@/i18n/I18nContext'
import type { Message, ToolStartEvent, ToolResultEvent } from '@/lib/database.types'

interface BranchIndicatorProps {
  branches: Message[]
  selectedId: string
  onSwitch: (childId: string) => void
}

function BranchIndicator({ branches, selectedId, onSwitch }: BranchIndicatorProps) {
  const idx = branches.findIndex((b) => b.id === selectedId)
  if (idx < 0) return null

  return (
    <div className="flex items-center gap-1 text-xs text-muted-foreground">
      <button
        disabled={idx === 0}
        onClick={() => idx > 0 && onSwitch(branches[idx - 1].id)}
        className="disabled:opacity-30 hover:text-foreground transition-colors"
      >
        <ChevronLeft className="h-3 w-3" />
      </button>
      <span className="tabular-nums">{idx + 1}/{branches.length}</span>
      <button
        disabled={idx === branches.length - 1}
        onClick={() => idx < branches.length - 1 && onSwitch(branches[idx + 1].id)}
        className="disabled:opacity-30 hover:text-foreground transition-colors"
      >
        <ChevronRight className="h-3 w-3" />
      </button>
    </div>
  )
}

interface MessageViewProps {
  messages: Message[]
  allMessages: Message[]
  streamingContent: string
  isStreaming: boolean
  activeTools?: ToolStartEvent[]
  toolResults?: ToolResultEvent[]
  activeAgent?: { agent: string; display_name: string } | null
  redactionStage?: 'anonymizing' | 'deanonymizing' | 'blocked' | null
  // Phase 11 SANDBOX-07 D-P11-02: live SSE buffer for execute_code streaming.
  // Plumbed from useChatState via ChatPage. Map is reset in 3 lifecycle sites
  // (handleSelectThread, sendMessageToThread enter/finally) — stale entries
  // for prior turns cannot collide with current panels because tool_call_id
  // is a UUID and CodeExecutionPanel only consults Map keys it knows about.
  sandboxStreams?: Map<string, { stdout: string[]; stderr: string[] }>
  onFork?: (messageId: string) => void
  onSwitchBranch?: (forkPointId: string, childId: string) => void
}

export function MessageView({
  messages,
  allMessages,
  streamingContent,
  isStreaming,
  activeTools = [],
  toolResults = [],
  activeAgent = null,
  redactionStage = null,
  sandboxStreams,
  onFork,
  onSwitchBranch,
}: MessageViewProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const childrenMap = useMemo(() => buildChildrenMap(allMessages), [allMessages])
  const { t } = useI18n()
  const isBlocked = redactionStage === 'blocked'

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent, activeTools, toolResults, activeAgent, redactionStage])

  if (messages.length === 0 && !isStreaming) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm text-muted-foreground">Send a message to start the conversation</p>
      </div>
    )
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col gap-4 p-4 overflow-y-auto">
      {messages.map((msg) => {
        const parentId = msg.parent_message_id ?? null
        const siblings = parentId ? childrenMap.get(parentId) : null
        const hasBranches = siblings && siblings.length > 1

        return (
          <div
            key={msg.id}
            className={`group flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-[75%] ${msg.role === 'user' ? '' : 'space-y-1'}`}>
              {msg.role === 'assistant' && msg.tool_calls?.agent && (
                <AgentBadge agent={msg.tool_calls.agent} />
              )}
              {msg.role === 'assistant' && msg.tool_calls?.calls && msg.tool_calls.calls.length > 0 && (
                <ToolCallList
                  toolCalls={msg.tool_calls.calls}
                  sandboxStreams={sandboxStreams}
                />
              )}
              <div
                className={`rounded-lg px-4 py-2 text-sm ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-br from-primary to-[oklch(0.40_0.15_260)] dark:to-[oklch(0.50_0.18_260)] text-primary-foreground'
                    : 'bg-muted/80 text-foreground backdrop-blur-sm'
                }`}
              >
                <div className="whitespace-pre-wrap break-words">{msg.content}</div>
              </div>
              <div className="flex items-center gap-2 mt-1">
                {hasBranches && onSwitchBranch && parentId && (
                  <BranchIndicator
                    branches={siblings}
                    selectedId={msg.id}
                    onSwitch={(childId) => onSwitchBranch(parentId, childId)}
                  />
                )}
                {onFork && !msg.id.startsWith('optimistic-') && (
                  <button
                    onClick={() => onFork(msg.id)}
                    className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-foreground transition-all"
                    title="Fork conversation here"
                  >
                    <GitFork className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>
          </div>
        )
      })}

      {isStreaming && !isBlocked && (
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
                input={at.input ?? {}}
                isLoading={true}
              />
            ))}

            {streamingContent && (
              <div className="rounded-lg px-4 py-2 bg-muted text-foreground">
                <StreamingMessage content={streamingContent} isStreaming={true} />
              </div>
            )}

            {!streamingContent && activeTools.length === 0 && toolResults.length === 0 && !activeAgent && (
              <div className="rounded-lg px-4 py-2 bg-muted text-foreground">
                <ThinkingIndicator />
              </div>
            )}
          </div>
        </div>
      )}

      {isBlocked && (
        <div className="flex justify-start" role="alert" aria-live="polite">
          <div className="max-w-[75%] rounded-lg border border-amber-500/40 bg-amber-500/10 dark:bg-amber-500/15 p-4">
            <div className="flex items-start gap-3">
              <ShieldAlert className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-amber-900 dark:text-amber-100">
                  {t('redactionBlockedTitle')}
                </p>
                <p className="text-xs text-amber-800 dark:text-amber-200/90 mt-1 leading-relaxed">
                  {t('redactionBlockedBody')}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
