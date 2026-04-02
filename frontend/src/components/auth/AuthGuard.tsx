import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '@/lib/supabase'

interface AuthGuardProps {
  children: React.ReactNode
}

export function AuthGuard({ children }: AuthGuardProps) {
  const navigate = useNavigate()
  const [checked, setChecked] = useState(false)
  const [authenticated, setAuthenticated] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) {
        setAuthenticated(true)
      } else {
        navigate('/auth')
      }
      setChecked(true)
    })

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) {
        navigate('/auth')
      }
    })

    return () => listener.subscription.unsubscribe()
  }, [navigate])

  if (!checked) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  return authenticated ? <>{children}</> : null
}
