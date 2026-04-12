import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Save, Shield, Globe, Bell, ChevronLeft, ChevronRight, Settings, User } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/contexts/AuthContext'
import { useI18n } from '@/i18n/I18nContext'
import type { Locale } from '@/i18n/translations'

interface UserPreferences {
  theme: string
  notifications_enabled: boolean
}

type SettingsSection = 'language' | 'notifications'

const LANGUAGES: { value: Locale; label: string }[] = [
  { value: 'id', label: 'Bahasa Indonesia' },
  { value: 'en', label: 'English' },
]

const SECTIONS: { id: SettingsSection; icon: typeof Globe; labelKey: string }[] = [
  { id: 'language', icon: Globe, labelKey: 'settings.language' },
  { id: 'notifications', icon: Bell, labelKey: 'settings.notifications' },
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
  const [panelCollapsed, setPanelCollapsed] = useState(false)

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
      {/* Column 2 — Settings nav panel */}
      {panelCollapsed ? (
        <div className="flex h-full w-[50px] shrink-0 flex-col items-center border-r border-border/50 py-4 gap-3">
          <button
            onClick={() => setPanelCollapsed(false)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            title={t('settings.title')}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <Settings className="h-4 w-4 text-muted-foreground" />
        </div>
      ) : (
      <div className="flex w-[340px] shrink-0 flex-col border-r border-border/50">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border/50 shrink-0">
          <div>
            <h1 className="text-sm font-semibold">{t('settings.title')}</h1>
            <p className="text-[10px] text-muted-foreground">Manage your preferences</p>
          </div>
          <button onClick={() => setPanelCollapsed(true)} className="text-muted-foreground hover:text-foreground transition-colors">
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
            </>
          )}
        </div>
      </div>
      )}

      {/* Column 3 — Settings content */}
      <div className="flex-1 flex flex-col overflow-y-auto">
        <div className="max-w-xl p-8 space-y-6">
          {activeSection === 'language' && (
            <section className="space-y-4">
              <div>
                <h2 className="text-sm font-semibold">{t('settings.language')}</h2>
                <p className="text-xs text-muted-foreground mt-0.5">{t('settings.languageDesc')}</p>
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
            <section className="space-y-4">
              <div>
                <h2 className="text-sm font-semibold">{t('settings.notifications')}</h2>
                <p className="text-xs text-muted-foreground mt-0.5">{t('settings.notificationsDesc')}</p>
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
        </div>
      </div>
    </div>
  )
}
