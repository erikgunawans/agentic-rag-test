import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Save, Shield, Globe, Bell, ChevronLeft, PanelLeftClose, Settings, User, Menu, FileText, ClipboardCheck, Users, KeyRound } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { useSidebar } from '@/hooks/useSidebar'
import { useAuth } from '@/contexts/AuthContext'
import { useI18n } from '@/i18n/I18nContext'
import type { Locale } from '@/i18n/translations'

interface UserPreferences {
  theme: string
  notifications_enabled: boolean
}

type SettingsSection = 'language' | 'notifications' | 'security'

const LANGUAGES: { value: Locale; label: string }[] = [
  { value: 'id', label: 'Bahasa Indonesia' },
  { value: 'en', label: 'English' },
]

const SECTIONS: { id: SettingsSection; icon: typeof Globe; labelKey: string }[] = [
  { id: 'language', icon: Globe, labelKey: 'settings.language' },
  { id: 'notifications', icon: Bell, labelKey: 'settings.notifications' },
  { id: 'security', icon: KeyRound, labelKey: 'settings.security' },
]

export function SettingsPage() {
  const navigate = useNavigate()
  const { isAdmin, user } = useAuth()
  const { t, locale, setLocale } = useI18n()
  const [prefs, setPrefs] = useState<UserPreferences | null>(null)
  const [notifications, setNotifications] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeSection, setActiveSection] = useState<SettingsSection>('language')
  const { panelCollapsed, togglePanel } = useSidebar()
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false)

  const loadPrefs = useCallback(async () => {
    const res = await apiFetch('/preferences')
    const data: UserPreferences = await res.json()
    setPrefs(data)
    setNotifications(data.notifications_enabled)
  }, [])

  useEffect(() => {
    loadPrefs()
  }, [loadPrefs])

  async function handleSave() {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      await apiFetch('/preferences', {
        method: 'PATCH',
        body: JSON.stringify({
          theme: 'dark',
          notifications_enabled: notifications,
        }),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      await loadPrefs()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save preferences')
    } finally {
      setSaving(false)
    }
  }

  const isDirty = prefs !== null && notifications !== prefs.notifications_enabled

  return (
    <div className="flex h-full">
      {/* Mobile panel trigger */}
      <button
        onClick={() => setMobilePanelOpen(true)}
        className="md:hidden fixed bottom-4 right-4 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg focus-ring"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Mobile panel overlay */}
      {mobilePanelOpen && (
        <div className="md:hidden fixed inset-0 z-40">
          <div className="mobile-backdrop" onClick={() => setMobilePanelOpen(false)} />
          <div className="mobile-panel bg-background border-r border-border/50 overflow-y-auto">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-border/50 shrink-0">
              <div>
                <h1 className="text-sm font-semibold">{t('settings.title')}</h1>
                <p className="text-[10px] text-muted-foreground">Kelola preferensi Anda</p>
              </div>
              <button onClick={() => setMobilePanelOpen(false)} className="text-muted-foreground hover:text-foreground transition-colors focus-ring">
                <ChevronLeft className="h-4 w-4" />
              </button>
            </div>

            {/* User info */}
            <div className="px-5 py-4 border-b border-border/50">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                  <User className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium truncate">{user?.email ?? 'User'}</p>
                  <p className="text-[10px] text-muted-foreground">{isAdmin ? 'Administrator' : 'User'}</p>
                </div>
              </div>
            </div>

            {/* Section nav */}
            <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
              {SECTIONS.map(({ id, icon: Icon, labelKey }) => (
                <button
                  key={id}
                  onClick={() => { setActiveSection(id); setMobilePanelOpen(false) }}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-xs font-medium transition-colors ${
                    activeSection === id ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5 shrink-0" />
                  {t(labelKey)}
                </button>
              ))}

              {isAdmin && (
                <>
                  <div className="my-3 border-t border-border/50" />
                  <button
                    onClick={() => navigate('/admin/settings')}
                    className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-xs font-medium text-amber-400 hover:bg-amber-500/10 transition-colors"
                  >
                    <Shield className="h-3.5 w-3.5 shrink-0" />
                    {t('settings.admin')}
                  </button>
                  <button
                    onClick={() => navigate('/admin/audit')}
                    className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-xs font-medium text-amber-400 hover:bg-amber-500/10 transition-colors"
                  >
                    <FileText className="h-3.5 w-3.5 shrink-0" />
                    {t('settings.auditTrail')}
                  </button>
                  <button
                    onClick={() => navigate('/admin/reviews')}
                    className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-xs font-medium text-amber-400 hover:bg-amber-500/10 transition-colors"
                  >
                    <ClipboardCheck className="h-3.5 w-3.5 shrink-0" />
                    {t('settings.reviewQueue')}
                  </button>
                  <button
                    onClick={() => navigate('/admin/users')}
                    className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-xs font-medium text-amber-400 hover:bg-amber-500/10 transition-colors"
                  >
                    <Users className="h-3.5 w-3.5 shrink-0" />
                    {t('settings.userManagement') || 'User Management'}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Column 2 — Settings nav panel */}
      {!panelCollapsed && (
      <div className="hidden md:flex w-[340px] shrink-0 flex-col border-r border-border/50 glass">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border/50 shrink-0">
          <div>
            <h1 className="text-sm font-semibold">{t('settings.title')}</h1>
            <p className="text-[10px] text-muted-foreground">Kelola preferensi Anda</p>
          </div>
          <button onClick={togglePanel} className="flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors focus-ring" title="Collapse sidebar">
            <PanelLeftClose className="h-4 w-4" />
          </button>
        </div>

        {/* User info */}
        <div className="px-5 py-4 border-b border-border/50">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
              <User className="h-4 w-4" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate">{user?.email ?? 'User'}</p>
              <p className="text-[10px] text-muted-foreground">{isAdmin ? 'Administrator' : 'User'}</p>
            </div>
          </div>
        </div>

        {/* Section nav */}
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
          {SECTIONS.map(({ id, icon: Icon, labelKey }) => (
            <button
              key={id}
              onClick={() => setActiveSection(id)}
              className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-xs font-medium transition-colors ${
                activeSection === id ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              }`}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              {t(labelKey)}
            </button>
          ))}

          {isAdmin && (
            <>
              <div className="my-3 border-t border-border/50" />
              <button
                onClick={() => navigate('/admin/settings')}
                className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-xs font-medium text-amber-400 hover:bg-amber-500/10 transition-colors"
              >
                <Shield className="h-3.5 w-3.5 shrink-0" />
                {t('settings.admin')}
              </button>
              <button
                onClick={() => navigate('/admin/audit')}
                className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-xs font-medium text-amber-400 hover:bg-amber-500/10 transition-colors"
              >
                <FileText className="h-3.5 w-3.5 shrink-0" />
                {t('settings.auditTrail')}
              </button>
              <button
                onClick={() => navigate('/admin/reviews')}
                className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-xs font-medium text-amber-400 hover:bg-amber-500/10 transition-colors"
              >
                <ClipboardCheck className="h-3.5 w-3.5 shrink-0" />
                {t('settings.reviewQueue')}
              </button>
            </>
          )}
        </div>
      </div>
      )}

      {/* Column 3 — Settings content */}
      <div className="flex-1 flex flex-col items-center justify-center overflow-y-auto">
        <div className="w-full max-w-md p-8 space-y-6">
          {activeSection === 'language' && (
            <section className="space-y-5">
              <div className="text-center">
                <Globe className="h-8 w-8 mx-auto text-muted-foreground/25 mb-3" strokeWidth={1.5} />
                <h2 className="text-base font-semibold">{t('settings.language')}</h2>
                <p className="text-xs text-muted-foreground mt-1">{t('settings.languageDesc')}</p>
              </div>
              <div className="space-y-2">
                {LANGUAGES.map((lang) => (
                  <label
                    key={lang.value}
                    className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                      locale === lang.value ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                    }`}
                  >
                    <input
                      type="radio"
                      name="language"
                      value={lang.value}
                      checked={locale === lang.value}
                      onChange={() => setLocale(lang.value)}
                      className="mt-0.5"
                    />
                    <p className="text-sm font-medium">{lang.label}</p>
                  </label>
                ))}
              </div>
            </section>
          )}

          {activeSection === 'notifications' && (
            <section className="space-y-5">
              <div className="text-center">
                <Bell className="h-8 w-8 mx-auto text-muted-foreground/25 mb-3" strokeWidth={1.5} />
                <h2 className="text-base font-semibold">{t('settings.notifications')}</h2>
                <p className="text-xs text-muted-foreground mt-1">{t('settings.notificationsDesc')}</p>
              </div>
              <label className="flex items-center gap-3 rounded-lg border p-3 cursor-pointer hover:bg-muted/50">
                <input
                  type="checkbox"
                  checked={notifications}
                  onChange={(e) => setNotifications(e.target.checked)}
                />
                <div>
                  <p className="text-sm font-medium">{t('settings.enableNotifications')}</p>
                  <p className="text-xs text-muted-foreground">{t('settings.enableNotificationsDesc')}</p>
                </div>
              </label>

              {error && <p className="text-sm text-destructive">{error}</p>}

              <Button onClick={handleSave} disabled={!isDirty || saving} className="w-full">
                <Save className="mr-2 h-4 w-4" />
                {saving ? t('settings.saving') : saved ? t('settings.saved') : t('settings.save')}
              </Button>
            </section>
          )}

          {activeSection === 'security' && (
            <section className="space-y-5">
              <div className="text-center">
                <KeyRound className="h-8 w-8 mx-auto text-muted-foreground/25 mb-3" strokeWidth={1.5} />
                <h2 className="text-base font-semibold">{t('settings.security') || 'Security'}</h2>
                <p className="text-xs text-muted-foreground mt-1">{t('settings.securityDesc') || 'Manage your account security settings'}</p>
              </div>

              <div className="rounded-lg border p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <Shield className="h-5 w-5 text-primary shrink-0" />
                  <div>
                    <p className="text-sm font-medium">{t('settings.mfa') || 'Two-Factor Authentication (TOTP)'}</p>
                    <p className="text-xs text-muted-foreground">{t('settings.mfaDesc') || 'Add an extra layer of security to your account using an authenticator app'}</p>
                  </div>
                </div>
                <div className="rounded-lg bg-amber-500/10 border border-amber-500/30 p-3">
                  <p className="text-xs text-amber-400">{t('settings.mfaNote') || 'MFA enrollment is managed through Supabase Auth. Contact your administrator to enable MFA requirement for the organization.'}</p>
                </div>
              </div>

              <div className="rounded-lg border p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <Settings className="h-5 w-5 text-muted-foreground shrink-0" />
                  <div>
                    <p className="text-sm font-medium">{t('settings.sessionTimeout') || 'Session Timeout'}</p>
                    <p className="text-xs text-muted-foreground">{t('settings.sessionTimeoutDesc') || 'Your session will expire after a period of inactivity (configured by admin)'}</p>
                  </div>
                </div>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
