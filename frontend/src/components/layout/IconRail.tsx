import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Home, Folder, FilePlus, GitCompare, ShieldCheck, Scale, Settings, LayoutGrid } from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { useAuth } from '@/contexts/AuthContext'
import { useI18n } from '@/i18n/I18nContext'
import { UserAvatar } from './UserAvatar'

const navItems = [
  { path: '/', icon: Home, labelKey: 'nav.chat', end: true },
  { path: '/documents', icon: Folder, labelKey: 'nav.documents' },
  { path: '/create', icon: FilePlus, labelKey: 'nav.create' },
  { path: '/compare', icon: GitCompare, labelKey: 'nav.compare' },
  { path: '/compliance', icon: ShieldCheck, labelKey: 'nav.compliance' },
  { path: '/analysis', icon: Scale, labelKey: 'nav.analysis' },
]

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
  const [flyoutOpen, setFlyoutOpen] = useState(false)

  return (
    <div className="flex h-full w-[60px] shrink-0 flex-col items-center border-r border-border bg-[var(--icon-rail)] py-4">
      <div className="mb-6 flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-lg font-bold text-primary-foreground">
        K
      </div>

      <nav className="flex flex-col items-center gap-2">
        {navItems.map(({ path, icon: Icon, labelKey, end }) => (
          <NavLink
            key={path}
            to={path}
            end={end}
            className={railButtonClass}
            aria-label={t(labelKey)}
            title={t(labelKey)}
          >
            <Icon className="h-5 w-5" />
          </NavLink>
        ))}
      </nav>

      <div className="mt-3 flex flex-col items-center">
        <Popover open={flyoutOpen} onOpenChange={setFlyoutOpen}>
          <PopoverTrigger
            className="flex h-10 w-10 items-center justify-center rounded-lg text-[var(--icon-rail-foreground)] hover:bg-accent hover:text-accent-foreground transition-colors"
            aria-label={t('nav.moreModules')}
            title={t('nav.moreModules')}
          >
            <LayoutGrid className="h-5 w-5" />
          </PopoverTrigger>
          <PopoverContent side="right" align="start" className="w-48 p-2">
            <p className="text-xs text-muted-foreground px-2 py-1">{t('nav.comingSoon')}</p>
          </PopoverContent>
        </Popover>
      </div>

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
