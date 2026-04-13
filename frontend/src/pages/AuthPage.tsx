import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '@/lib/supabase'
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
    <div
      className="flex min-h-screen items-start justify-center pt-[10vh] sm:pt-[12vh]"
      style={{ backgroundColor: '#161617' }}
    >
      {/* Card — no border, no shadow, just a shade lighter */}
      <div
        className="w-full max-w-[580px] mx-4 rounded-[20px] px-14 pt-14 pb-12 sm:px-20 sm:pt-16 sm:pb-14"
        style={{ backgroundColor: '#232326' }}
      >
        {/* Icon + Title */}
        <div className="flex flex-col items-center mb-12">
          <div
            className="flex h-16 w-16 items-center justify-center rounded-full mb-6"
            style={{ backgroundColor: '#333338' }}
          >
            <Sparkles className="h-7 w-7" style={{ color: '#e8e8ed' }} />
          </div>
          <h1
            className="text-[28px] font-semibold tracking-tight text-center"
            style={{ color: '#f5f5f7' }}
          >
            {tab === 'login' ? t('auth.title') : t('auth.signupTitle') || 'Buat Akun'}
          </h1>
          <p className="text-[14px] mt-2 text-center" style={{ color: '#86868b' }}>
            {t('auth.subtitle')}
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {/* Email */}
          <div className="mb-4">
            <input
              id="email"
              type="email"
              placeholder={t('auth.email')}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="w-full rounded-[12px] px-4 py-[14px] text-[17px] text-white/90 placeholder:text-[#56565a] focus:outline-none focus:ring-2 focus:ring-[#0071e3]/60 transition-all"
              style={{ backgroundColor: '#1a1a1d', border: '1px solid #3d3d42' }}
            />
          </div>

          {/* Password */}
          <div className="mb-3">
            <input
              id="password"
              type="password"
              placeholder={t('auth.password')}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
              className="w-full rounded-[12px] px-4 py-[14px] text-[17px] text-white/90 placeholder:text-[#56565a] focus:outline-none focus:ring-2 focus:ring-[#0071e3]/60 transition-all"
              style={{ backgroundColor: '#1a1a1d', border: '1px solid #3d3d42' }}
            />
          </div>

          {/* Toggle link */}
          <div className="mb-8">
            <button
              type="button"
              onClick={() => { setTab(tab === 'login' ? 'signup' : 'login'); setError(''); setMessage('') }}
              className="text-[14px] hover:underline"
              style={{ color: '#2997ff' }}
            >
              {tab === 'login' ? t('auth.signup') || 'Buat Akun Baru' : t('auth.login') || 'Sudah punya akun? Masuk'}
            </button>
          </div>

          {/* Error / Message */}
          {error && <p className="text-[13px] mb-4" style={{ color: '#ff453a' }}>{error}</p>}
          {message && <p className="text-[13px] mb-4" style={{ color: '#30d158' }}>{message}</p>}

          {/* Info section */}
          <div className="flex items-start gap-3 mb-8">
            <Shield className="h-6 w-6 shrink-0 mt-0.5" style={{ color: '#2997ff' }} />
            <p className="text-[13px] leading-[1.6]" style={{ color: '#86868b' }}>
              {t('auth.securityNote') || 'Data Anda digunakan untuk masuk secara aman dan mengakses layanan. Kami menerapkan enkripsi untuk keamanan dan pelaporan.'}
            </p>
          </div>

          {/* Buttons — two side by side like Apple */}
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={loading}
              className="flex-1 h-[44px] rounded-[10px] text-[15px] font-medium text-white disabled:opacity-50 transition-colors"
              style={{ backgroundColor: '#0071e3' }}
              onMouseEnter={(e) => { if (!loading) e.currentTarget.style.backgroundColor = '#0077ed' }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#0071e3' }}
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <span className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                </span>
              ) : tab === 'login' ? t('auth.login') : t('auth.signup')}
            </button>
            <button
              type="button"
              onClick={() => { setTab(tab === 'login' ? 'signup' : 'login'); setError(''); setMessage('') }}
              className="flex-1 h-[44px] rounded-[10px] text-[15px] font-medium transition-colors"
              style={{ backgroundColor: '#323236', color: '#f5f5f7' }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#3a3a3e'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#323236'}
            >
              {tab === 'login' ? t('auth.signup') || 'Daftar' : t('auth.login') || 'Masuk'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
