import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '@/lib/supabase'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useI18n } from '@/i18n/I18nContext'

type Tab = 'login' | 'signup'

export function AuthPage() {
  const navigate = useNavigate()
  const { t } = useI18n()
  const [tab, setTab] = useState<Tab>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)

    try {
      if (tab === 'login') {
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
        navigate('/')
      } else {
        const { error } = await supabase.auth.signUp({ email, password })
        if (error) throw error
        setMessage(t('auth.confirmEmail'))
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t('auth.error'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <div className="w-full max-w-sm space-y-6 rounded-lg border p-8 shadow-sm">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t('auth.title')}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t('auth.subtitle')}</p>
        </div>

        {/* Tabs */}
        <div className="flex rounded-md border p-1 gap-1">
          {(['login', 'signup'] as Tab[]).map((tabKey) => (
            <button
              key={tabKey}
              onClick={() => setTab(tabKey)}
              className={`flex-1 rounded py-1.5 text-sm font-medium transition-colors ${
                tab === tabKey ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {tabKey === 'login' ? t('auth.login') : t('auth.signup')}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="email">{t('auth.email')}</label>
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="password">{t('auth.password')}</label>
            <Input
              id="password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
          {message && <p className="text-sm text-green-400">{message}</p>}

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? t('auth.loading') : tab === 'login' ? t('auth.login') : t('auth.signup')}
          </Button>
        </form>
      </div>
    </div>
  )
}
