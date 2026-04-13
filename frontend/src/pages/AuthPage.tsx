import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '@/lib/supabase'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n/I18nContext'
import { Sparkles, Shield } from 'lucide-react'

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
    <div className="flex min-h-screen items-center justify-center bg-[oklch(0.10_0.02_260)] relative overflow-hidden">
      {/* Subtle ambient glow */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[500px] w-[500px] rounded-full bg-primary/[0.04] blur-[120px]" />

      {/* Card */}
      <div className="relative z-10 w-full max-w-[480px] mx-4">
        <div className="rounded-2xl bg-[oklch(0.16_0.015_260/0.8)] backdrop-blur-2xl border border-white/[0.08] shadow-[0_8px_60px_rgba(0,0,0,0.5),0_0_0_1px_rgba(255,255,255,0.03)] px-10 py-12 sm:px-14 sm:py-14">

          {/* Logo */}
          <div className="flex flex-col items-center mb-10">
            <div className="relative mb-6">
              {/* Decorative ring */}
              <div className="absolute inset-0 -m-4 rounded-full border border-primary/20 animate-[spin_20s_linear_infinite]" />
              <div className="absolute inset-0 -m-7 rounded-full border border-primary/10 animate-[spin_30s_linear_infinite_reverse]" />
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-[oklch(0.55_0.20_280)] shadow-[0_4px_20px_rgba(124,58,237,0.3)]">
                <Sparkles className="h-8 w-8 text-white" />
              </div>
            </div>
            <h1 className="text-[22px] font-semibold tracking-tight text-white">
              {tab === 'login' ? t('auth.title') : t('auth.signupTitle') || 'Buat Akun'}
            </h1>
            <p className="text-[13px] text-white/50 mt-1.5">{t('auth.subtitle')}</p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email */}
            <div>
              <label className="block text-[11px] font-medium text-white/40 uppercase tracking-wider mb-2" htmlFor="email">
                {t('auth.email')}
              </label>
              <input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full rounded-xl bg-white/[0.06] border border-white/[0.08] px-4 py-3.5 text-sm text-white placeholder:text-white/25 focus:outline-none focus:border-primary/50 focus:bg-white/[0.08] transition-all duration-200"
              />
            </div>

            {/* Password */}
            <div>
              <label className="block text-[11px] font-medium text-white/40 uppercase tracking-wider mb-2" htmlFor="password">
                {t('auth.password')}
              </label>
              <input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full rounded-xl bg-white/[0.06] border border-white/[0.08] px-4 py-3.5 text-sm text-white placeholder:text-white/25 focus:outline-none focus:border-primary/50 focus:bg-white/[0.08] transition-all duration-200"
              />
            </div>

            {/* Error / Message */}
            {error && (
              <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2.5">
                <p className="text-[13px] text-red-400">{error}</p>
              </div>
            )}
            {message && (
              <div className="rounded-lg bg-green-500/10 border border-green-500/20 px-4 py-2.5">
                <p className="text-[13px] text-green-400">{message}</p>
              </div>
            )}

            {/* Submit */}
            <div className="pt-2">
              <Button
                type="submit"
                disabled={loading}
                className="w-full h-12 rounded-xl text-sm font-semibold bg-gradient-to-r from-primary to-[oklch(0.55_0.20_280)] hover:from-primary/90 hover:to-[oklch(0.55_0.20_280/0.9)] shadow-[0_4px_16px_rgba(124,58,237,0.25)] transition-all duration-200"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                    {t('auth.loading')}
                  </span>
                ) : tab === 'login' ? t('auth.login') : t('auth.signup')}
              </Button>
            </div>
          </form>

          {/* Divider */}
          <div className="flex items-center gap-4 my-7">
            <div className="flex-1 h-px bg-white/[0.06]" />
            <span className="text-[11px] text-white/25 uppercase tracking-wider">atau</span>
            <div className="flex-1 h-px bg-white/[0.06]" />
          </div>

          {/* Toggle tab */}
          <button
            onClick={() => { setTab(tab === 'login' ? 'signup' : 'login'); setError(''); setMessage('') }}
            className="w-full h-12 rounded-xl border border-white/[0.08] bg-white/[0.03] text-sm font-medium text-white/70 hover:bg-white/[0.06] hover:text-white transition-all duration-200"
          >
            {tab === 'login' ? t('auth.signup') || 'Daftar' : t('auth.login') || 'Masuk'}
          </button>

          {/* Footer note */}
          <div className="flex items-center justify-center gap-2 mt-8">
            <Shield className="h-3.5 w-3.5 text-white/20" />
            <p className="text-[11px] text-white/25 text-center">
              {t('auth.securityNote') || 'Data Anda dilindungi dengan enkripsi end-to-end'}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
