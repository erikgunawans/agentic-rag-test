import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Home, Folder, Settings, Shield, LogOut } from 'lucide-react'
import { IconRailNew } from '@/components/shared/IconRailNew'
import { SidebarProvider, useSidebar } from './SidebarContext'
import { useAuth } from '@/contexts/AuthContext'
import { supabase } from '@/lib/supabase'

function AppLayoutInner() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, isAdmin } = useAuth()
  const { content: sidebarContent, width: sidebarWidth } = useSidebar()

  const pathname = location.pathname

  const mainIcons = [
    {
      icon: Home,
      id: 'chat',
      isActive: pathname === '/',
      onClick: () => navigate('/'),
    },
    {
      icon: Folder,
      id: 'documents',
      isActive: pathname.startsWith('/documents'),
      onClick: () => navigate('/documents'),
    },
    {
      icon: Settings,
      id: 'settings',
      isActive: pathname.startsWith('/settings'),
      onClick: () => navigate('/settings'),
    },
  ]

  const groupItems = [
    ...(isAdmin
      ? [
          {
            id: 'admin',
            icon: Shield,
            label: 'Admin Settings',
            isActive: pathname.startsWith('/admin'),
          },
        ]
      : []),
    {
      id: 'logout',
      icon: LogOut,
      label: 'Sign Out',
    },
  ]

  const activeGroupItemId = pathname.startsWith('/admin') ? 'admin' : null

  function handleGroupItemClick(id: string) {
    if (id === 'admin') {
      navigate('/admin/settings')
    } else if (id === 'logout') {
      supabase.auth.signOut()
    }
  }

  const initials = user?.email
    ? user.email.substring(0, 2).toUpperCase()
    : '??'

  return (
    <div className="flex h-screen overflow-hidden bg-bg-deep">
      {/* Column 1: Icon Rail */}
      <div className="flex items-center justify-center w-[88px] shrink-0">
        <IconRailNew
          mainIcons={mainIcons}
          groupItems={groupItems}
          activeGroupItemId={activeGroupItemId}
          onGroupItemClick={handleGroupItemClick}
          userInitials={initials}
          userOnline
        />
      </div>

      {/* Column 2: Sidebar (set by each page via SidebarContext) */}
      {sidebarContent && (
        <div
          className="shrink-0 bg-bg-surface border-r border-border-subtle overflow-hidden"
          style={{ width: sidebarWidth }}
        >
          {sidebarContent}
        </div>
      )}

      {/* Column 3: Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden bg-mesh-gradient">
        <Outlet />
      </div>
    </div>
  )
}

export default function AppLayout() {
  return (
    <SidebarProvider>
      <AppLayoutInner />
    </SidebarProvider>
  )
}
