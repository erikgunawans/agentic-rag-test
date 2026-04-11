import { createContext, useContext } from 'react'
import type { useChatState } from '@/hooks/useChatState'

type ChatContextValue = ReturnType<typeof useChatState>

const ChatContext = createContext<ChatContextValue | null>(null)

export const ChatProvider = ChatContext.Provider

export function useChatContext() {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChatContext must be used within ChatProvider')
  return ctx
}
