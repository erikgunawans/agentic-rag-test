import { supabase } from '@/lib/supabase'
import { LogOut } from 'lucide-react'
import { useState } from 'react'
import { useI18n } from '@/i18n/I18nContext'

export function deriveDisplayName(email: string): string {
  const prefix = email.split('@')[0]
  return prefix
    .split(/[._-]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

export function getInitials(email: string): string {
  const parts = email.split('@')[0].split(/[._-]/)
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase()
  }
  return parts[0].substring(0, 2).toUpperCase()
}

interface UserAvatarProps {
  email: string
}

export function UserAvatar({ email }: UserAvatarProps) {
  const { t } = useI18n()
  const [showMenu, setShowMenu] = useState(false)
  const initials = getInitials(email)

  async function handleSignOut() {
    await supabase.auth.signOut()
  }

  return (
    <div className="relative">
      <button
        onClick={() => setShowMenu(!showMenu)}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground transition-opacity hover:opacity-80"
        aria-label="User menu"
      >
        {initials}
      </button>

      {showMenu && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
          <div className="absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 rounded-lg border border-border bg-popover p-1 shadow-lg">
            <button
              onClick={handleSignOut}
              className="flex w-full items-center gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm text-popover-foreground transition-colors hover:bg-accent"
            >
              <LogOut className="h-4 w-4" />
              {t('nav.signOut')}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
