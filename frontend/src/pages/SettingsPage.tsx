import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Save, Shield } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { useAuth } from '@/contexts/AuthContext'
import { useI18n } from '@/i18n/I18nContext'
import type { Locale } from '@/i18n/translations'

interface UserPreferences {
  theme: string
  notifications_enabled: boolean
}

const LANGUAGES: { value: Locale; label: string }[] = [
  { value: 'id', label: 'Bahasa Indonesia' },
  { value: 'en', label: 'English' },
]

export function SettingsPage() {
  const navigate = useNavigate()
  const { isAdmin } = useAuth()
  const { t, locale, setLocale } = useI18n()
  const [prefs, setPrefs] = useState<UserPreferences | null>(null)
  const [notifications, setNotifications] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-2xl space-y-8">
        <h1 className="text-lg font-semibold">{t('settings.title')}</h1>

        {/* Admin link */}
        {isAdmin && (
          <>
            <section className="space-y-3">
              <div>
                <h2 className="text-sm font-semibold">{t('settings.admin')}</h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t('settings.adminDesc')}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/admin/settings')}
                className="gap-2"
              >
                <Shield className="h-4 w-4 text-amber-500" />
                {t('settings.admin')}
              </Button>
            </section>
            <Separator />
          </>
        )}

        {/* Language */}
        <section className="space-y-3">
          <div>
            <h2 className="text-sm font-semibold">{t('settings.language')}</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {t('settings.languageDesc')}
            </p>
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

        <Separator />

        {/* Notifications */}
        <section className="space-y-3">
          <div>
            <h2 className="text-sm font-semibold">{t('settings.notifications')}</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {t('settings.notificationsDesc')}
            </p>
          </div>
          <label className="flex items-center gap-3 rounded-lg border p-3 cursor-pointer hover:bg-muted/50">
            <input
              type="checkbox"
              checked={notifications}
              onChange={(e) => setNotifications(e.target.checked)}
            />
            <div>
              <p className="text-sm font-medium">{t('settings.enableNotifications')}</p>
              <p className="text-xs text-muted-foreground">
                {t('settings.enableNotificationsDesc')}
              </p>
            </div>
          </label>
        </section>

        {/* Save */}
        {error && <p className="text-sm text-destructive">{error}</p>}

        <Button onClick={handleSave} disabled={!isDirty || saving} className="w-full">
          <Save className="mr-2 h-4 w-4" />
          {saving ? t('settings.saving') : saved ? t('settings.saved') : t('settings.save')}
        </Button>
      </div>
    </div>
  )
}
