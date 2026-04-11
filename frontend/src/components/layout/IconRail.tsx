import { useLocation, useNavigate } from 'react-router-dom'
import { MessageSquare, FileText, Settings } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import { useI18n } from '@/i18n/I18nContext'
import { UserAvatar } from './UserAvatar'

export function IconRail() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { t } = useI18n()

  const navItems = [
    { path: '/', icon: MessageSquare, label: t('nav.chat') },
    { path: '/documents', icon: FileText, label: t('nav.documents') },
  ]

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  return (
    <div className="flex h-full w-[60px] shrink-0 flex-col items-center border-r border-border bg-[var(--icon-rail)] py-4">
      {/* Brand logo */}
      <div className="mb-6 flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-lg font-bold text-primary-foreground">
        K
      </div>

      {/* Nav icons */}
      <nav className="flex flex-col items-center gap-2">
        {navItems.map(({ path, icon: Icon, label }) => (
          <button
            key={path}
            onClick={() => navigate(path)}
            className={`flex h-10 w-10 items-center justify-center rounded-lg transition-colors ${
              isActive(path)
                ? 'bg-primary text-primary-foreground'
                : 'text-[var(--icon-rail-foreground)] hover:bg-accent hover:text-accent-foreground'
            }`}
            aria-label={label}
            title={label}
          >
            <Icon className="h-5 w-5" />
          </button>
        ))}
      </nav>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Bottom: Settings + Avatar */}
      <div className="flex flex-col items-center gap-3">
        <button
          onClick={() => navigate('/settings')}
          className={`flex h-10 w-10 items-center justify-center rounded-lg transition-colors ${
            isActive('/settings')
              ? 'bg-primary text-primary-foreground'
              : 'text-[var(--icon-rail-foreground)] hover:bg-accent hover:text-accent-foreground'
          }`}
          aria-label={t('nav.settings')}
          title={t('nav.settings')}
        >
          <Settings className="h-5 w-5" />
        </button>

        {user?.email && <UserAvatar email={user.email} />}
      </div>
    </div>
  )
}
