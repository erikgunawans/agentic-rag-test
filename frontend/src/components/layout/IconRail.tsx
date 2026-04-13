import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Home, Folder, FilePlus, Library, GitCompare, ShieldCheck, Scale, ClipboardList, FileCheck, BookOpen, Plug, LayoutDashboard, Settings, LayoutGrid, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
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
]

const moreItems = [
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
        <img src="/lexcore-logo-dark.svg" alt="LexCore" className="h-9 w-9 rounded-lg object-contain" />
        {showPanelToggle && onTogglePanel && (
          <Tooltip>
            <TooltipTrigger
              onClick={onTogglePanel}
              className="flex h-8 w-8 items-center justify-center rounded-md text-[var(--icon-rail-foreground)] hover:bg-accent hover:text-accent-foreground transition-all duration-200 focus-ring"
            >
              <ToggleIcon className="h-4 w-4" />
            </TooltipTrigger>
            <TooltipContent side="right" sideOffset={8}>
              {panelCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            </TooltipContent>
          </Tooltip>
        )}
      </div>

      <nav className="flex flex-col items-center gap-2 overflow-y-auto overflow-x-hidden flex-1 min-h-0 scrollbar-hide">
        {navItems.map(({ path, icon: Icon, labelKey, end }) => (
          <Tooltip key={path}>
            <TooltipTrigger asChild>
              <NavLink
                to={path}
                end={end}
                className={railButtonClass}
                aria-label={t(labelKey)}
              >
                <Icon className="h-5 w-5" />
              </NavLink>
            </TooltipTrigger>
            <TooltipContent side="right" sideOffset={8}>
              {t(labelKey)}
            </TooltipContent>
          </Tooltip>
        ))}
      </nav>

      <div className="mt-3 flex flex-col items-center">
        <Popover open={flyoutOpen} onOpenChange={setFlyoutOpen}>
          <Tooltip>
            <TooltipTrigger asChild>
              <PopoverTrigger
                className="flex h-11 w-11 items-center justify-center rounded-lg text-[var(--icon-rail-foreground)] hover:bg-accent hover:text-accent-foreground transition-all duration-200"
                aria-label={t('nav.moreModules')}
              >
                <LayoutGrid className="h-5 w-5" />
              </PopoverTrigger>
            </TooltipTrigger>
            <TooltipContent side="right" sideOffset={8}>
              {t('nav.moreModules')}
            </TooltipContent>
          </Tooltip>
          <PopoverContent side="right" align="start" className="w-48 p-2 space-y-0.5">
            {moreItems.map(({ path, icon: Icon, labelKey }) => (
              <NavLink
                key={path}
                to={path}
                onClick={() => setFlyoutOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                    isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                  }`
                }
                aria-label={t(labelKey)}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {t(labelKey)}
              </NavLink>
            ))}
          </PopoverContent>
        </Popover>
      </div>

      <div className="flex flex-col items-center gap-3 mt-3">
        <Tooltip>
          <TooltipTrigger asChild>
            <NavLink
              to="/settings"
              className={railButtonClass}
              aria-label={t('nav.settings')}
            >
              <Settings className="h-5 w-5" />
            </NavLink>
          </TooltipTrigger>
          <TooltipContent side="right" sideOffset={8}>
            {t('nav.settings')}
          </TooltipContent>
        </Tooltip>
        {user?.email && <UserAvatar email={user.email} />}
      </div>
    </div>
  )
}
