import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'

interface SidebarState {
  content: ReactNode
  width: number
}

interface SidebarContextValue extends SidebarState {
  setSidebar: (content: ReactNode, width?: number) => void
  clearSidebar: () => void
}

const SidebarContext = createContext<SidebarContextValue>({
  content: null,
  width: 260,
  setSidebar: () => {},
  clearSidebar: () => {},
})

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SidebarState>({ content: null, width: 260 })

  const setSidebar = useCallback((content: ReactNode, width = 260) => {
    setState({ content, width })
  }, [])

  const clearSidebar = useCallback(() => {
    setState({ content: null, width: 260 })
  }, [])

  return (
    <SidebarContext.Provider value={{ ...state, setSidebar, clearSidebar }}>
      {children}
    </SidebarContext.Provider>
  )
}

export function useSidebar() {
  return useContext(SidebarContext)
}
