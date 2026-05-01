import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Home, Folder, FilePlus, Library, GitCompare, ShieldCheck, ShieldAlert, Scale, ClipboardList, FileCheck, BookOpen, Plug, LayoutDashboard, Settings, PanelLeftClose, PanelLeftOpen, Clock, Zap } from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { useAuth } from '@/contexts/AuthContext'
import { useI18n } from '@/i18n/I18nContext'
import { UserAvatar } from './UserAvatar'
import { Logo } from '@/components/shared/Logo'
import type { LucideIcon } from 'lucide-react'

interface NavItem {
  path: string
  icon: LucideIcon
  labelKey: string
  end?: boolean
}

interface NavGroup {
  labelKey: string
  icon: LucideIcon
  children: NavItem[]
}

const standaloneItems: NavItem[] = [
  { path: '/', icon: Home, labelKey: 'nav.chat', end: true },
  { path: '/skills', icon: Zap, labelKey: 'nav.skills' },
  { path: '/dashboard', icon: LayoutDashboard, labelKey: 'nav.dashboard' },
  { path: '/bjr', icon: Scale, labelKey: 'nav.bjr' },
  { path: '/pdp', icon: ShieldAlert, labelKey: 'nav.pdp' },
]

const groups: NavGroup[] = [
  {
    labelKey: 'nav.documentsGroup',
    icon: Folder,
    children: [
      { path: '/documents', icon: Folder, labelKey: 'nav.documents' },
      { path: '/create', icon: FilePlus, labelKey: 'nav.create' },
      { path: '/compare', icon: GitCompare, labelKey: 'nav.compare' },
    ],
  },
  {
    labelKey: 'nav.legalTools',
    icon: Scale,
    children: [
      { path: '/clause-library', icon: Library, labelKey: 'nav.clauseLibrary' },
      { path: '/compliance', icon: ShieldCheck, labelKey: 'nav.compliance' },
      { path: '/compliance/timeline', icon: Clock, labelKey: 'nav.complianceTimeline' },
      { path: '/analysis', icon: Scale, labelKey: 'nav.analysis' },
      { path: '/obligations', icon: ClipboardList, labelKey: 'nav.obligations' },
    ],
  },
  {
    labelKey: 'nav.governance',
    icon: ShieldCheck,
    children: [
      { path: '/approvals', icon: FileCheck, labelKey: 'nav.approvals' },
      { path: '/regulatory', icon: BookOpen, labelKey: 'nav.regulatory' },
      { path: '/integrations', icon: Plug, labelKey: 'nav.integrations' },
    ],
  },
]

function railButtonClass({ isActive }: { isActive: boolean }) {
  return `flex h-11 w-11 items-center justify-center rounded-lg transition-all duration-200 focus-ring ${
    isActive
      ? 'bg-primary/15 text-primary relative before:absolute before:left-0 before:top-1 before:bottom-1 before:w-[3px] before:rounded-full before:bg-gradient-to-b before:from-primary before:to-[var(--gradient-accent-to)]'
      : 'text-[var(--icon-rail-foreground)] hover:bg-accent hover:text-accent-foreground'
  }`
}

interface IconRailProps {
  panelCollapsed?: boolean
  onTogglePanel?: () => void
  showPanelToggle?: boolean
}

function GroupPopover({ group }: { group: NavGroup }) {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const { t } = useI18n()

  const isActive = group.children.some(child =>
    child.end ? location.pathname === child.path : location.pathname.startsWith(child.path)
  )

  const Icon = group.icon

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <div className="relative">
        {isActive && (
          <div className="absolute left-0 top-1 bottom-1 w-[3px] rounded-full bg-gradient-to-b from-primary to-[var(--gradient-accent-to)]" />
        )}
        <Tooltip open={open ? false : undefined}>
          <TooltipTrigger asChild>
            <PopoverTrigger
              className={`flex h-11 w-11 items-center justify-center rounded-lg transition-all duration-200 focus-ring ${
                isActive
                  ? 'bg-primary/15 text-primary'
                  : 'text-[var(--icon-rail-foreground)] hover:bg-accent hover:text-accent-foreground'
              }`}
              aria-label={t(group.labelKey)}
            >
              <Icon className="h-5 w-5" />
            </PopoverTrigger>
          </TooltipTrigger>
          <TooltipContent side="right" sideOffset={8}>
            {t(group.labelKey)}
          </TooltipContent>
        </Tooltip>
      </div>
      <PopoverContent side="right" align="start" className="w-52 p-2">
        <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {t(group.labelKey)}
        </p>
        <div className="space-y-0.5">
          {group.children.map(({ path, icon: ChildIcon, labelKey }) => (
            <NavLink
              key={path}
              to={path}
              onClick={() => setOpen(false)}
              className={({ isActive: childActive }) =>
                `flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                  childActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                }`
              }
              aria-label={t(labelKey)}
            >
              <ChildIcon className="h-4 w-4 shrink-0" />
              {t(labelKey)}
            </NavLink>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}

export function IconRail({ panelCollapsed, onTogglePanel, showPanelToggle }: IconRailProps) {
  const { user } = useAuth()
  const { t } = useI18n()

  const ToggleIcon = panelCollapsed ? PanelLeftOpen : PanelLeftClose

  return (
    <div className="flex h-full w-[60px] shrink-0 flex-col items-center border-r border-border bg-[var(--icon-rail)] py-4">
      <div className="flex flex-col items-center gap-2 mb-6">
        <Logo variant="icon" className="h-9 w-9 rounded-lg object-contain" />
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

      <nav className="flex flex-col items-center gap-2 flex-1 min-h-0">
        {/* Standalone: Chat + Dashboard */}
        {standaloneItems.map(({ path, icon: Icon, labelKey, end }) => (
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

        {/* Separator */}
        <div className="w-6 h-px bg-border my-1" />

        {/* Groups: Documents, Legal Tools, Governance */}
        {groups.map((group) => (
          <GroupPopover key={group.labelKey} group={group} />
        ))}
      </nav>

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
