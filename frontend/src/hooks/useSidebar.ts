import { useOutletContext } from 'react-router-dom'
import type { SidebarContext } from '@/layouts/AppLayout'

export function useSidebar() {
  return useOutletContext<SidebarContext>()
}
