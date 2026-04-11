import { NavLink } from 'react-router-dom'
import { MessageSquare, FileText, Settings } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import { useI18n } from '@/i18n/I18nContext'
import { UserAvatar } from './UserAvatar'

function railButtonClass({ isActive }: { isActive: boolean }) {
  return `flex h-10 w-10 items-center justify-center rounded-lg transition-colors ${
    isActive
      ? 'bg-primary text-primary-foreground'
      : 'text-[var(--icon-rail-foreground)] hover:bg-accent hover:text-accent-foreground'
  }`
}

export function IconRail() {
  const { user } = useAuth()
  const { t } = useI18n()

  const navItems = [
    { path: '/', icon: MessageSquare, label: t('nav.chat') },
    { path: '/documents', icon: FileText, label: t('nav.documents') },
  ]

  return (
    <div className="flex h-full w-[60px] shrink-0 flex-col items-center border-r border-border bg-[var(--icon-rail)] py-4">
      <div className="mb-6 flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-lg font-bold text-primary-foreground">
        K
      </div>

      <nav className="flex flex-col items-center gap-2">
        {navItems.map(({ path, icon: Icon, label }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            className={railButtonClass}
            aria-label={label}
            title={label}
          >
            <Icon className="h-5 w-5" />
          </NavLink>
        ))}
      </nav>

      <div className="flex-1" />

      <div className="flex flex-col items-center gap-3">
        <NavLink
          to="/settings"
          className={railButtonClass}
          aria-label={t('nav.settings')}
          title={t('nav.settings')}
        >
          <Settings className="h-5 w-5" />
        </NavLink>

        {user?.email && <UserAvatar email={user.email} />}
      </div>
    </div>
  )
}
