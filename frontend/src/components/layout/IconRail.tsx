import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Home, Folder, FilePlus, Library, GitCompare, ShieldCheck, Scale, ClipboardList, FileCheck, BookOpen, Plug, LayoutDashboard, Settings, LayoutGrid, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { useAuth } from '@/contexts/AuthContext'
import { useI18n } from '@/i18n/I18nContext'
import { UserAvatar } from './UserAvatar'

const navItems = [
  { path: '/dashboard', icon: LayoutDashboard, labelKey: 'nav.dashboard' },
  { path: '/', icon: Home, labelKey: 'nav.chat', end: true },
  { path: '/documents', icon: Folder, labelKey: 'nav.documents' },
  { path: '/create', icon: FilePlus, labelKey: 'nav.create' },
  { path: '/clause-library', icon: Library, labelKey: 'nav.clauseLibrary' },
  { path: '/compare', icon: GitCompare, labelKey: 'nav.compare' },
  { path: '/compliance', icon: ShieldCheck, labelKey: 'nav.compliance' },
  { path: '/analysis', icon: Scale, labelKey: 'nav.analysis' },
  { path: '/obligations', icon: ClipboardList, labelKey: 'nav.obligations' },
  { path: '/approvals', icon: FileCheck, labelKey: 'nav.approvals' },
  { path: '/regulatory', icon: BookOpen, labelKey: 'nav.regulatory' },
  { path: '/integrations', icon: Plug, labelKey: 'nav.integrations' },
]

function railButtonClass({ isActive }: { isActive: boolean }) {
  return `flex h-11 w-11 items-center justify-center rounded-lg transition-all duration-200 focus-ring ${
    isActive
      ? 'bg-primary/15 text-primary relative before:absolute before:left-0 before:top-1 before:bottom-1 before:w-[3px] before:rounded-full before:bg-gradient-to-b before:from-primary before:to-[oklch(0.65_0.18_230)]'
      : 'text-[var(--icon-rail-foreground)] hover:bg-accent hover:text-accent-foreground'
  }`
}

interface IconRailProps {
  panelCollapsed?: boolean
  onTogglePanel?: () => void
  showPanelToggle?: boolean
}

export function IconRail({ panelCollapsed, onTogglePanel, showPanelToggle }: IconRailProps) {
  const { user } = useAuth()
  const { t } = useI18n()
  const [flyoutOpen, setFlyoutOpen] = useState(false)

  const ToggleIcon = panelCollapsed ? PanelLeftOpen : PanelLeftClose

  return (
    <div className="flex h-full w-[60px] shrink-0 flex-col items-center border-r border-border bg-[var(--icon-rail)] glass py-4">
      <div className="flex flex-col items-center gap-2 mb-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-lg font-bold text-primary-foreground">
          K
        </div>
        {showPanelToggle && onTogglePanel && (
          <button
            onClick={onTogglePanel}
            className="flex h-8 w-8 items-center justify-center rounded-md text-[var(--icon-rail-foreground)] hover:bg-accent hover:text-accent-foreground transition-all duration-200 focus-ring"
            title={panelCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <ToggleIcon className="h-4 w-4" />
          </button>
        )}
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
            className="flex h-11 w-11 items-center justify-center rounded-lg text-[var(--icon-rail-foreground)] hover:bg-accent hover:text-accent-foreground transition-all duration-200"
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
