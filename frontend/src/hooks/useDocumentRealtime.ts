import { useEffect } from 'react'
import { supabase } from '@/lib/supabase'
import type { Document } from '@/lib/database.types'

export function useDocumentRealtime(
  userId: string | undefined,
  onUpdate: (doc: Document) => void,
) {
  useEffect(() => {
    if (!userId) return

    const channel = supabase
      .channel('document-status')
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'documents',
          filter: `user_id=eq.${userId}`,
        },
        (payload) => {
          onUpdate(payload.new as Document)
        },
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [userId, onUpdate])
}
