import { useCallback, useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { apiFetch } from '@/lib/api'
import { ThreadList } from '@/components/chat/ThreadList'
import { MessageView } from '@/components/chat/MessageView'
import { MessageInput } from '@/components/chat/MessageInput'
import { useNavigate } from 'react-router-dom'
import { Separator } from '@/components/ui/separator'
import { LogOut, FileText, Settings } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { Thread, Message, SSEEvent, ToolStartEvent, ToolResultEvent } from '@/lib/database.types'

export function ChatPage() {
  const navigate = useNavigate()
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [activeTools, setActiveTools] = useState<ToolStartEvent[]>([])
  const [toolResults, setToolResults] = useState<ToolResultEvent[]>([])
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

    // Fetch messages for this thread from Supabase directly
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
  }

  async function handleDeleteThread(threadId: string) {
    await apiFetch(`/threads/${threadId}`, { method: 'DELETE' })
    setThreads((prev) => prev.filter((t) => t.id !== threadId))
    if (activeThreadId === threadId) {
      setActiveThreadId(null)
      setMessages([])
    }
  }

  async function handleSendMessage(content: string) {
    if (!activeThreadId || isStreaming) return

    // Optimistic user message
    const optimisticMsg: Message = {
      id: `optimistic-${Date.now()}`,
      thread_id: activeThreadId,
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

    try {
      const response = await apiFetch('/chat/stream', {
        method: 'POST',
        body: JSON.stringify({ thread_id: activeThreadId, message: content }),
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

          if (event.type === 'tool_start') {
            setActiveTools((prev) => [...prev, event])
          } else if (event.type === 'tool_result') {
            // Move from active to completed — match by tool name
            setActiveTools((prev) => {
              const idx = prev.findIndex((t) => t.tool === event.tool)
              if (idx >= 0) return [...prev.slice(0, idx), ...prev.slice(idx + 1)]
              return prev
            })
            setToolResults((prev) => [...prev, event])
          } else {
            // Delta event (type === 'delta' or missing type for backward compat)
            const delta = 'delta' in event ? event.delta : ''
            const isDone = 'done' in event ? event.done : false
            if (!isDone && delta) {
              assistantContent += delta
              setStreamingContent(assistantContent)
            }
          }
        }
      }

      // Replace optimistic messages with persisted ones
      const { data } = await supabase
        .from('messages')
        .select('*')
        .eq('thread_id', activeThreadId)
        .order('created_at', { ascending: true })

      setMessages((data as Message[]) ?? [])

      // Refresh thread list to update updated_at ordering
      loadThreads()
    } finally {
      setIsStreaming(false)
      setStreamingContent('')
      setActiveTools([])
      setToolResults([])
    }
  }

  async function handleSignOut() {
    await supabase.auth.signOut()
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <div className="w-64 shrink-0 flex flex-col border-r">
        <div className="p-4 border-b flex items-center justify-between">
          <span className="font-semibold text-sm">RAG Chat</span>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" onClick={() => navigate('/documents')} aria-label="Documents">
              <FileText className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" onClick={() => navigate('/settings')} aria-label="Settings">
              <Settings className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" onClick={handleSignOut} aria-label="Sign out">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <div className="flex-1 overflow-hidden">
          <ThreadList
            threads={threads}
            activeThreadId={activeThreadId}
            onSelect={handleSelectThread}
            onCreate={handleCreateThread}
            onDelete={handleDeleteThread}
            loading={loadingThreads}
          />
        </div>
      </div>

      <Separator orientation="vertical" />

      {/* Main chat area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {activeThreadId ? (
          <>
            <MessageView
              messages={messages}
              streamingContent={streamingContent}
              isStreaming={isStreaming}
              activeTools={activeTools}
              toolResults={toolResults}
            />
            <MessageInput onSend={handleSendMessage} disabled={isStreaming} />
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <div className="text-center space-y-2">
              <p className="text-muted-foreground text-sm">Select a thread or create a new one</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
