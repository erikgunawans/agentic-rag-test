import { useState, useEffect } from 'react'
import { Users, UserX, UserCheck, Search, Shield } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { apiFetch } from '@/lib/api'

interface UserProfile {
  id: string
  user_id: string
  display_name: string | null
  department: string | null
  is_active: boolean
  deactivated_at: string | null
  last_login_at: string | null
  created_at: string
}

const inputBase = "w-full rounded-lg bg-secondary text-foreground px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
const inputClass = `${inputBase} border border-border`

export function UserManagementPage() {
  const { t } = useI18n()
  const [users, setUsers] = useState<UserProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  useEffect(() => {
    loadUsers()
  }, [])

  async function loadUsers() {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch('/admin/users')
      const data = await res.json()
      setUsers(data.data ?? data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  async function handleDeactivate(user: UserProfile) {
    const confirmed = confirm(
      `Are you sure you want to deactivate ${user.display_name || user.user_id}? They will lose access immediately.`
    )
    if (!confirmed) return

    setActionLoading(user.id)
    try {
      await apiFetch(`/admin/users/${user.id}/deactivate`, { method: 'PATCH' })
      await loadUsers()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to deactivate user')
    } finally {
      setActionLoading(null)
    }
  }

  async function handleReactivate(user: UserProfile) {
    setActionLoading(user.id)
    try {
      await apiFetch(`/admin/users/${user.id}/reactivate`, { method: 'PATCH' })
      await loadUsers()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to reactivate user')
    } finally {
      setActionLoading(null)
    }
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleString('id-ID', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  }

  const filtered = users.filter(u => {
    const q = search.toLowerCase()
    if (!q) return true
    return (
      (u.display_name?.toLowerCase().includes(q)) ||
      (u.department?.toLowerCase().includes(q))
    )
  })

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-[800px] mx-auto space-y-6">
        {/* Header */}
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Shield className="h-5 w-5 text-amber-400" />
            <h1 className="text-lg font-semibold">{t('userManagement.title')}</h1>
            <span className="rounded-full bg-amber-500/15 px-2.5 py-0.5 text-xs font-medium text-amber-400">
              Admin
            </span>
          </div>
          <p className="text-sm text-muted-foreground ml-8">
            Manage user accounts, activate or deactivate access.
          </p>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder={t('userManagement.search')}
            className={`${inputClass} pl-9`}
          />
        </div>

        {/* Error */}
        {error && (
          <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* User list */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <Users className="h-10 w-10 mb-3 opacity-40" />
            <p className="text-sm">{t('userManagement.empty')}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map(user => (
              <div
                key={user.id}
                className="flex items-center gap-4 rounded-lg border border-border/50 bg-card px-4 py-3 transition-colors hover:bg-accent/30"
              >
                {/* Avatar placeholder */}
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-medium text-muted-foreground">
                  {(user.display_name?.[0] ?? '?').toUpperCase()}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">
                      {user.display_name || 'Unnamed User'}
                    </span>
                    {/* Status badge */}
                    {user.is_active ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-green-500/15 px-2 py-0.5 text-xs font-medium text-green-400">
                        <UserCheck className="h-3 w-3" />
                        {t('userManagement.active')}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-red-500/15 px-2 py-0.5 text-xs font-medium text-red-400">
                        <UserX className="h-3 w-3" />
                        {t('userManagement.deactivated')}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 text-xs text-muted-foreground">
                    {user.department && <span>{user.department}</span>}
                    <span>Joined {formatDate(user.created_at)}</span>
                    {!user.is_active && user.deactivated_at && (
                      <span className="text-red-400/70">
                        Deactivated {formatDate(user.deactivated_at)}
                      </span>
                    )}
                  </div>
                </div>

                {/* Action */}
                <div className="shrink-0">
                  {user.is_active ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDeactivate(user)}
                      disabled={actionLoading === user.id}
                      className="gap-1.5 border-red-500/30 text-red-400 hover:bg-red-500/10 hover:text-red-300"
                    >
                      <UserX className="h-3.5 w-3.5" />
                      {t('userManagement.deactivate')}
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleReactivate(user)}
                      disabled={actionLoading === user.id}
                      className="gap-1.5 border-green-500/30 text-green-400 hover:bg-green-500/10 hover:text-green-300"
                    >
                      <UserCheck className="h-3.5 w-3.5" />
                      {t('userManagement.reactivate')}
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
