import { useCallback, useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { apiFetch } from '@/lib/api'
import type { Thread, Message, SSEEvent, ToolStartEvent, ToolResultEvent } from '@/lib/database.types'

export function useChatState() {
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [activeTools, setActiveTools] = useState<ToolStartEvent[]>([])
  const [toolResults, setToolResults] = useState<ToolResultEvent[]>([])
  const [activeAgent, setActiveAgent] = useState<{ agent: string; display_name: string } | null>(null)
  const [loadingThreads, setLoadingThreads] = useState(false)

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

  async function handleSelectThread(threadId: string) {
    setActiveThreadId(threadId)
    setMessages([])
    setStreamingContent('')

    const { data } = await supabase
      .from('messages')
      .select('*')
      .eq('thread_id', threadId)
      .order('created_at', { ascending: true })

    setMessages((data as Message[]) ?? [])
  }

  async function handleCreateThread() {
    const res = await apiFetch('/threads', {
      method: 'POST',
      body: JSON.stringify({ title: 'New Thread' }),
    })
    const thread: Thread = await res.json()
    setThreads((prev) => [thread, ...prev])
    setActiveThreadId(thread.id)
    setMessages([])
    setStreamingContent('')
    return thread
  }

  async function handleDeleteThread(threadId: string) {
    await apiFetch(`/threads/${threadId}`, { method: 'DELETE' })
    setThreads((prev) => prev.filter((t) => t.id !== threadId))
    if (activeThreadId === threadId) {
      setActiveThreadId(null)
      setMessages([])
    }
  }

  async function sendMessageToThread(threadId: string, content: string) {
    const optimisticMsg: Message = {
      id: `optimistic-${Date.now()}`,
      thread_id: threadId,
      user_id: '',
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, optimisticMsg])
    setIsStreaming(true)
    setStreamingContent('')
    setActiveTools([])
    setToolResults([])
    setActiveAgent(null)

    try {
      const response = await apiFetch('/chat/stream', {
        method: 'POST',
        body: JSON.stringify({ thread_id: threadId, message: content }),
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
          const event = JSON.parse(line.slice(6)) as SSEEvent

          if (event.type === 'agent_start') {
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

      const { data } = await supabase
        .from('messages')
        .select('*')
        .eq('thread_id', threadId)
        .order('created_at', { ascending: true })

      setMessages((data as Message[]) ?? [])
      loadThreads()
    } finally {
      setIsStreaming(false)
      setStreamingContent('')
      setActiveTools([])
      setToolResults([])
      setActiveAgent(null)
    }
  }

  async function handleSendMessage(content: string) {
    if (!activeThreadId || isStreaming) return
    await sendMessageToThread(activeThreadId, content)
  }

  async function handleSendFirstMessage(content: string) {
    if (isStreaming) return
    const thread = await handleCreateThread()
    await sendMessageToThread(thread.id, content)
  }

  return {
    threads,
    activeThreadId,
    messages,
    isStreaming,
    streamingContent,
    activeTools,
    toolResults,
    activeAgent,
    loadingThreads,
    handleSelectThread,
    handleCreateThread,
    handleDeleteThread,
    handleSendMessage,
    handleSendFirstMessage,
  }
}
