import { useCallback, useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { apiFetch } from '@/lib/api'
import { ChatSidebar } from '@/components/chat/ChatSidebar'
import { MessageView } from '@/components/chat/MessageView'
import { MessageInput } from '@/components/chat/MessageInput'
import { ChatInputCard } from '@/components/chat/ChatInputCard'
import { QuickActionGrid } from '@/components/chat/QuickActionGrid'
import { useAuth } from '@/contexts/AuthContext'
import { useSidebar } from '@/layouts/SidebarContext'
import { Sparkles } from 'lucide-react'
import type { Thread, Message, SSEEvent, ToolStartEvent, ToolResultEvent } from '@/lib/database.types'

export function ChatPage() {
  const { user } = useAuth()
  const { setSidebar, clearSidebar } = useSidebar()
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

  // Set sidebar via context
  useEffect(() => {
    setSidebar(
      <ChatSidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onSelect={handleSelectThread}
        onCreate={handleCreateThread}
        onDelete={handleDeleteThread}
        loading={loadingThreads}
      />,
      260,
    )
    return () => clearSidebar()
  })

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

  async function handleSendMessage(content: string, threadId?: string) {
    const tid = threadId ?? activeThreadId
    if (!tid || isStreaming) return

    const optimisticMsg: Message = {
      id: `optimistic-${Date.now()}`,
      thread_id: tid,
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
        body: JSON.stringify({ thread_id: tid, message: content }),
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
        .eq('thread_id', tid)
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

  // Send from the home welcome screen: create thread first, then send
  async function handleSendFromHome(content: string) {
    const thread = await handleCreateThread()
    await handleSendMessage(content, thread.id)
  }

  // Extract display name from email
  const userName = user?.email
    ? user.email.split('@')[0].replace(/[._-]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : 'User'

  if (activeThreadId) {
    // Active chat view
    return (
      <div className="flex flex-1 flex-col overflow-hidden">
        <MessageView
          messages={messages}
          streamingContent={streamingContent}
          isStreaming={isStreaming}
          activeTools={activeTools}
          toolResults={toolResults}
          activeAgent={activeAgent}
        />
        <MessageInput onSend={handleSendMessage} disabled={isStreaming} />
      </div>
    )
  }

  // Welcome / home view
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6">
      {/* Hero greeting */}
      <div className="flex items-center gap-3.5 mb-3">
        <Sparkles size={44} className="text-white" />
        <h1 className="text-4xl font-bold tracking-tight">
          <span className="text-foreground">Hi, </span>
          <span className="bg-gradient-to-r from-accent-gradient-start via-accent-gradient-mid to-accent-gradient-end bg-clip-text text-transparent">
            {userName}
          </span>
        </h1>
      </div>

      {/* Subtitle */}
      <p className="text-base text-muted-foreground text-center max-w-[560px] leading-relaxed mb-8">
        Ask questions about your documents, contracts, and compliance requirements
      </p>

      {/* Input Card */}
      <ChatInputCard onSend={handleSendFromHome} disabled={isStreaming} />

      {/* Quick Action Bento Grid */}
      <QuickActionGrid />
    </div>
  )
}
