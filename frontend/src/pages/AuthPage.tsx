import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '@/lib/supabase'
import { useI18n } from '@/i18n/I18nContext'
import { Shield } from 'lucide-react'

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
    <div className="flex min-h-screen items-start justify-center pt-[8vh] sm:pt-[10vh]" style={{ backgroundColor: '#000000' }}>

      {/* Floating card */}
      <div
        className="w-full max-w-[580px] mx-4 rounded-[18px] px-12 pt-12 pb-10 sm:px-16 sm:pt-14 sm:pb-12"
        style={{
          backgroundColor: '#1d1d1f',
          boxShadow: '0 2px 8px rgba(0,0,0,0.4), 0 12px 40px rgba(0,0,0,0.5), 0 0 0 0.5px rgba(255,255,255,0.06)',
        }}
      >

        {/* Pointillist logo halo */}
        <div className="flex flex-col items-center mb-10">
          <div className="relative mb-6">
            <svg width="120" height="120" viewBox="0 0 120 120" className="block">
              {Array.from({ length: 40 }).map((_, i) => {
                const angle = (i / 40) * Math.PI * 2 - Math.PI / 2
                const r = 48
                const x = 60 + Math.cos(angle) * r
                const y = 60 + Math.sin(angle) * r
                const hue = (i / 40) * 300 + 20
                return (
                  <circle
                    key={i}
                    cx={x}
                    cy={y}
                    r={3.2 - (i % 3) * 0.4}
                    fill={`hsl(${hue}, 80%, 65%)`}
                    opacity={0.85}
                  />
                )
              })}
              <text x="60" y="68" textAnchor="middle" fill="#f5f5f7" fontSize="32" fontWeight="600" fontFamily="-apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif">K</text>
            </svg>
          </div>

          <h1 className="text-[28px] font-bold tracking-tight text-center" style={{ color: '#f5f5f7', fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif' }}>
            {tab === 'login' ? t('auth.title') : t('auth.signupTitle') || 'Buat Akun'}
          </h1>
          <p className="text-[15px] mt-2 text-center" style={{ color: '#86868b' }}>
            {t('auth.subtitle')}
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {/* Email input — transparent bg, subtle border */}
          <div className="mb-4 mx-auto" style={{ maxWidth: '400px' }}>
            <input
              id="email"
              type="email"
              placeholder={t('auth.email')}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="w-full rounded-[12px] px-4 py-[14px] text-[17px] placeholder:text-[#48484a] focus:outline-none transition-all"
              style={{ backgroundColor: 'transparent', border: '1px solid #424245', color: '#f5f5f7' }}
              onFocus={(e) => e.currentTarget.style.borderColor = '#0071e3'}
              onBlur={(e) => e.currentTarget.style.borderColor = '#424245'}
            />
          </div>

          {/* Password input */}
          <div className="mb-3 mx-auto" style={{ maxWidth: '400px' }}>
            <input
              id="password"
              type="password"
              placeholder={t('auth.password')}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
              className="w-full rounded-[12px] px-4 py-[14px] text-[17px] placeholder:text-[#48484a] focus:outline-none transition-all"
              style={{ backgroundColor: 'transparent', border: '1px solid #424245', color: '#f5f5f7' }}
              onFocus={(e) => e.currentTarget.style.borderColor = '#0071e3'}
              onBlur={(e) => e.currentTarget.style.borderColor = '#424245'}
            />
          </div>

          {/* Create account / switch link */}
          <div className="mb-10 mx-auto" style={{ maxWidth: '400px' }}>
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
          {error && <p className="text-[13px] mb-4 text-center" style={{ color: '#ff453a' }}>{error}</p>}
          {message && <p className="text-[13px] mb-4 text-center" style={{ color: '#30d158' }}>{message}</p>}

          {/* Security info */}
          <div className="flex items-start gap-3 mb-8 mx-auto" style={{ maxWidth: '420px' }}>
            <Shield className="h-6 w-6 shrink-0 mt-0.5" style={{ color: '#2997ff' }} />
            <p className="text-[12px] leading-[1.65] text-center" style={{ color: '#86868b' }}>
              {t('auth.securityNote') || 'Data Anda digunakan untuk masuk secara aman dan mengakses layanan. Kami menerapkan enkripsi untuk keamanan dan pelaporan.'}
            </p>
          </div>

          {/* Two pill buttons side by side */}
          <div className="flex gap-3 mx-auto" style={{ maxWidth: '420px' }}>
            {/* Primary: deep blue pill */}
            <button
              type="submit"
              disabled={loading}
              className="flex-1 h-[46px] rounded-[12px] text-[15px] font-medium text-white disabled:opacity-50 transition-colors"
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

            {/* Secondary: white/grey pill */}
            <button
              type="button"
              onClick={() => { setTab(tab === 'login' ? 'signup' : 'login'); setError(''); setMessage('') }}
              className="flex-1 h-[46px] rounded-[12px] text-[15px] font-medium transition-colors"
              style={{ backgroundColor: '#e8e8ed', color: '#1d1d1f' }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#d2d2d7'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#e8e8ed'}
            >
              {tab === 'login' ? t('auth.signup') || 'Daftar' : t('auth.login') || 'Masuk'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
