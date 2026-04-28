import { useCallback, useEffect, useRef, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { apiFetch } from '@/lib/api'
import { buildChildrenMap, getActivePath } from '@/lib/messageTree'
import type { Thread, Message, SSEEvent, ToolStartEvent, ToolResultEvent } from '@/lib/database.types'

export function useChatState() {
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const [allMessages, setAllMessages] = useState<Message[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [branchSelections, setBranchSelections] = useState<Map<string, string>>(new Map())
  const branchSelectionsRef = useRef(branchSelections)
  branchSelectionsRef.current = branchSelections
  const [forkParentId, setForkParentId] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [activeTools, setActiveTools] = useState<ToolStartEvent[]>([])
  const [toolResults, setToolResults] = useState<ToolResultEvent[]>([])
  const [activeAgent, setActiveAgent] = useState<{ agent: string; display_name: string } | null>(null)
  // Phase 5 D-88 + D-94: redaction status spinner state.
  // Set on backend redaction_status events; null when redaction is OFF or between turns.
  const [redactionStage, setRedactionStage] = useState<
    'anonymizing' | 'deanonymizing' | 'blocked' | null
  >(null)
  const [loadingThreads, setLoadingThreads] = useState(false)
  // ADR-0008: per-thread sticky web-search toggle; resets on thread switch
  const [webSearchEnabled, setWebSearchEnabled] = useState(false)

  const loadThreads = useCallback(async () => {
    setLoadingThreads(true)
    try {
      const res = await apiFetch('/threads')
      const data: Thread[] = await res.json()
      setThreads(data)
    } finally {
      setLoadingThreads(false)
    }
  }, [])

  useEffect(() => {
    loadThreads()
  }, [loadThreads])

  useEffect(() => {
    setWebSearchEnabled(false) // ADR-0008: per-thread sticky; reset on thread switch
  }, [activeThreadId])

  function rebuildVisibleMessages(all: Message[], selections: Map<string, string>) {
    const childrenMap = buildChildrenMap(all)
    setMessages(getActivePath(childrenMap, selections))
  }

  async function handleSelectThread(threadId: string) {
    setActiveThreadId(threadId)
    setStreamingContent('')
    setRedactionStage(null)
    setForkParentId(null)
    const newSelections = new Map<string, string>()
    setBranchSelections(newSelections)

    const { data } = await supabase
      .from('messages')
      .select('*')
      .eq('thread_id', threadId)
      .order('created_at', { ascending: true })

    const all = (data as Message[]) ?? []
    setAllMessages(all)
    rebuildVisibleMessages(all, newSelections)
  }

  async function handleCreateThread() {
    const res = await apiFetch('/threads', {
      method: 'POST',
      body: JSON.stringify({ title: 'New Thread' }),
    })
    const thread: Thread = await res.json()
    setThreads((prev) => [thread, ...prev])
    setActiveThreadId(thread.id)
    setAllMessages([])
    setMessages([])
    setBranchSelections(new Map())
    setForkParentId(null)
    setStreamingContent('')
    setRedactionStage(null)
    return thread
  }

  async function handleDeleteThread(threadId: string) {
    await apiFetch(`/threads/${threadId}`, { method: 'DELETE' })
    setThreads((prev) => prev.filter((t) => t.id !== threadId))
    if (activeThreadId === threadId) {
      setActiveThreadId(null)
      setAllMessages([])
      setMessages([])
    }
  }

  function handleSwitchBranch(forkPointId: string, selectedChildId: string) {
    const newSelections = new Map(branchSelections)
    newSelections.set(forkPointId, selectedChildId)
    setBranchSelections(newSelections)
    rebuildVisibleMessages(allMessages, newSelections)
  }

  function handleForkAt(messageId: string) {
    setForkParentId(messageId)
  }

  function handleCancelFork() {
    setForkParentId(null)
  }

  async function sendMessageToThread(threadId: string, content: string) {
    // Determine parent: if forking, use forkParentId; otherwise use the last visible message
    const parentId = forkParentId ?? messages[messages.length - 1]?.id ?? null

    const optimisticMsg: Message = {
      id: `optimistic-${Date.now()}`,
      thread_id: threadId,
      user_id: '',
      role: 'user',
      content,
      parent_message_id: parentId,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, optimisticMsg])
    setIsStreaming(true)
    setStreamingContent('')
    setActiveTools([])
    setToolResults([])
    setActiveAgent(null)
    setRedactionStage(null)
    setForkParentId(null)

    try {
      const response = await apiFetch('/chat/stream', {
        method: 'POST',
        body: JSON.stringify({
          thread_id: threadId,
          message: content,
          parent_message_id: parentId,
          web_search: webSearchEnabled, // ADR-0008
        }),
      })

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let assistantContent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          let event: SSEEvent
          try {
            event = JSON.parse(line.slice(6)) as SSEEvent
          } catch {
            continue
          }

          if (event.type === 'thread_title') {
            setThreads((prev) =>
              prev.map((t) =>
                t.id === event.thread_id ? { ...t, title: event.title } : t
              )
            )
          } else if (event.type === 'agent_start') {
            setActiveAgent({ agent: event.agent, display_name: event.display_name })
          } else if (event.type === 'agent_done') {
            setActiveAgent(null)
          } else if (event.type === 'tool_start') {
            setActiveTools((prev) => [...prev, event])
          } else if (event.type === 'tool_result') {
            setActiveTools((prev) => {
              const idx = prev.findIndex((t) => t.tool === event.tool)
              if (idx >= 0) return [...prev.slice(0, idx), ...prev.slice(idx + 1)]
              return prev
            })
            setToolResults((prev) => [...prev, event])
          } else if (event.type === 'redaction_status') {
            // Phase 5 D-88: status spinner state during the buffer window.
            setRedactionStage(event.stage)
            if (event.stage === 'blocked') {
              // D-94 egress trip — partial text is invalid; clear it.
              setStreamingContent('')
              assistantContent = ''
            }
          } else {
            const delta = 'delta' in event ? event.delta : ''
            const isDone = 'done' in event ? event.done : false
            if (!isDone && delta) {
              assistantContent += delta
              setStreamingContent(assistantContent)
            }
          }
        }
      }

      // Refetch all messages and rebuild tree
      const { data } = await supabase
        .from('messages')
        .select('*')
        .eq('thread_id', threadId)
        .order('created_at', { ascending: true })

      const all = (data as Message[]) ?? []
      setAllMessages(all)
      rebuildVisibleMessages(all, branchSelectionsRef.current)
      loadThreads()
    } finally {
      setIsStreaming(false)
      setStreamingContent('')
      setActiveTools([])
      setToolResults([])
      setActiveAgent(null)
      // D-94: keep `redactionStage === 'blocked'` visible after the stream ends so
      // the user sees the explanation card. It is reset on the next handleSendMessage.
      setRedactionStage((prev) => (prev === 'blocked' ? 'blocked' : null))
    }
  }

  async function handleSendMessage(content: string) {
    if (!activeThreadId || isStreaming) return
    await sendMessageToThread(activeThreadId, content)
  }

  function handleNewChat() {
    setActiveThreadId(null)
    setAllMessages([])
    setMessages([])
    setBranchSelections(new Map())
    setForkParentId(null)
    setStreamingContent('')
    setRedactionStage(null)
  }

  async function handleSendFirstMessage(content: string) {
    if (isStreaming) return
    const thread = await handleCreateThread()
    await sendMessageToThread(thread.id, content)
  }

  return {
    threads,
    activeThreadId,
    allMessages,
    messages,
    forkParentId,
    isStreaming,
    streamingContent,
    activeTools,
    toolResults,
    activeAgent,
    redactionStage,
    loadingThreads,
    webSearchEnabled,
    setWebSearchEnabled,
    handleSelectThread,
    handleCreateThread,
    handleDeleteThread,
    handleSendMessage,
    handleNewChat,
    handleSendFirstMessage,
    handleSwitchBranch,
    handleForkAt,
    handleCancelFork,
  }
}
