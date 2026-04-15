import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '@/lib/supabase'
import { useI18n } from '@/i18n/I18nContext'
import { useTheme } from '@/theme/ThemeContext'
import { Shield } from 'lucide-react'

type Tab = 'login' | 'signup'

export function AuthPage() {
  const navigate = useNavigate()
  const { t } = useI18n()
  const { resolvedTheme } = useTheme()
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

  const logoSrc = resolvedTheme === 'dark' ? '/lexcore-full-dark.svg' : '/lexcore-full-light.svg'

  return (
    <div className="flex min-h-screen items-start justify-center pt-[8vh] sm:pt-[10vh] bg-background">

      {/* Floating card */}
      <div className="w-full max-w-[580px] mx-4 rounded-[18px] px-12 pt-12 pb-10 sm:px-16 sm:pt-14 sm:pb-12 bg-card shadow-lg border border-border/50">

        {/* Logo */}
        <div className="flex flex-col items-center mb-10">
          <img src={logoSrc} alt="LexCore" className="h-20 mb-6" />
          <h1 className="text-[28px] font-bold tracking-tight text-center text-foreground">
            {tab === 'login' ? t('auth.title') : t('auth.signupTitle') || 'Buat Akun'}
          </h1>
          <p className="text-[15px] mt-2 text-center text-muted-foreground">
            {t('auth.subtitle')}
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {/* Email input */}
          <div className="mb-4 mx-auto max-w-[400px]">
            <input
              id="email"
              type="email"
              placeholder={t('auth.email')}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="w-full rounded-[12px] px-4 py-[14px] text-[17px] bg-transparent border border-border text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary transition-all"
            />
          </div>

          {/* Password input */}
          <div className="mb-3 mx-auto max-w-[400px]">
            <input
              id="password"
              type="password"
              placeholder={t('auth.password')}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
              className="w-full rounded-[12px] px-4 py-[14px] text-[17px] bg-transparent border border-border text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary transition-all"
            />
          </div>

          {/* Create account / switch link */}
          <div className="mb-10 mx-auto max-w-[400px]">
            <button
              type="button"
              onClick={() => { setTab(tab === 'login' ? 'signup' : 'login'); setError(''); setMessage('') }}
              className="text-[14px] hover:underline text-primary"
            >
              {tab === 'login' ? t('auth.signup') || 'Buat Akun Baru' : t('auth.login') || 'Sudah punya akun? Masuk'}
            </button>
          </div>

          {/* Error / Message */}
          {error && <p className="text-[13px] mb-4 text-center text-destructive">{error}</p>}
          {message && <p className="text-[13px] mb-4 text-center text-green-600 dark:text-green-400">{message}</p>}

          {/* Security info */}
          <div className="flex items-start gap-3 mb-8 mx-auto max-w-[420px]">
            <Shield className="h-6 w-6 shrink-0 mt-0.5 text-primary" />
            <p className="text-[12px] leading-[1.65] text-center text-muted-foreground">
              {t('auth.securityNote') || 'Data Anda digunakan untuk masuk secara aman dan mengakses layanan. Kami menerapkan enkripsi untuk keamanan dan pelaporan.'}
            </p>
          </div>

          {/* Two pill buttons side by side */}
          <div className="flex gap-3 mx-auto max-w-[420px]">
            {/* Primary: blue pill */}
            <button
              type="submit"
              disabled={loading}
              className="flex-1 h-[46px] rounded-[12px] text-[15px] font-medium text-white disabled:opacity-50 transition-colors bg-[#0071e3] hover:bg-[#0077ed]"
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <span className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                </span>
              ) : tab === 'login' ? t('auth.login') : t('auth.signup')}
            </button>

            {/* Secondary pill */}
            <button
              type="button"
              onClick={() => { setTab(tab === 'login' ? 'signup' : 'login'); setError(''); setMessage('') }}
              className="flex-1 h-[46px] rounded-[12px] text-[15px] font-medium transition-colors bg-secondary text-secondary-foreground hover:bg-secondary/80"
            >
              {tab === 'login' ? t('auth.signup') || 'Daftar' : t('auth.login') || 'Masuk'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
