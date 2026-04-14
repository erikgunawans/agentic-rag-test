import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

interface AdminGuardProps {
  children: React.ReactNode
}

export function AdminGuard({ children }: AdminGuardProps) {
  const navigate = useNavigate()
  const { isAdmin, loading } = useAuth()

  useEffect(() => {
    if (!loading && !isAdmin) {
      navigate('/')
    }
  }, [loading, isAdmin, navigate])

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  return isAdmin ? <>{children}</> : null
}
