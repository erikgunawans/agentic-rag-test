import { createContext, useContext } from 'react'
import type { useChatState } from '@/hooks/useChatState'

// Phase 19 / D-24: ChatContextValue is the full return type of useChatState,
// which now includes agentStatus, setAgentStatus, and tasks slices (Plan 19-07).
// Phase 20 / Plan 20-10 / UPL-04: also includes uploadingFiles, startUpload,
// updateUploadProgress, completeUpload, failUpload for FileUploadButton.
type ChatContextValue = ReturnType<typeof useChatState>

const ChatContext = createContext<ChatContextValue | null>(null)

export const ChatProvider = ChatContext.Provider

export function useChatContext() {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChatContext must be used within ChatProvider')
  return ctx
}
