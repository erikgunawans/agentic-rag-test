import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import type { User } from '@supabase/supabase-js'

interface AuthState {
  user: User | null
  role: string
  isAdmin: boolean
  loading: boolean
}

const AuthContext = createContext<AuthState>({
  user: null,
  role: 'user',
  isAdmin: false,
  loading: true,
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [role, setRole] = useState('user')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const u = data.session?.user ?? null
      setUser(u)
      const r = (u?.app_metadata?.role as string) ?? 'user'
      setRole(r)
      setLoading(false)
    })

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      const u = session?.user ?? null
      setUser(u)
      const r = (u?.app_metadata?.role as string) ?? 'user'
      setRole(r)
      setLoading(false)
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  const isAdmin = role === 'super_admin'

  return (
    <AuthContext.Provider value={{ user, role, isAdmin, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
