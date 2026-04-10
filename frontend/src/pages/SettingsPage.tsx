import { useCallback, useEffect, useState } from 'react'
import { Save } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { ColumnHeader } from '@/components/shared/ColumnHeader'
import { useSidebar } from '@/layouts/SidebarContext'

interface UserPreferences {
  theme: string
  notifications_enabled: boolean
}

const THEMES = [
  { value: 'system', label: 'System', description: 'Follow your OS preference' },
  { value: 'light', label: 'Light', description: 'Always use light mode' },
  { value: 'dark', label: 'Dark', description: 'Always use dark mode' },
]

function SettingsSidebar() {
  return (
    <div className="flex flex-col h-full">
      <ColumnHeader title="Settings" subtitle="Preferences" rightIcon="none" />
    </div>
  )
}

export function SettingsPage() {
  const { setSidebar, clearSidebar } = useSidebar()
  const [prefs, setPrefs] = useState<UserPreferences | null>(null)
  const [theme, setTheme] = useState('system')
  const [notifications, setNotifications] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadPrefs = useCallback(async () => {
    const res = await apiFetch('/preferences')
    const data: UserPreferences = await res.json()
    setPrefs(data)
    setTheme(data.theme)
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
          theme,
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

  useEffect(() => {
    setSidebar(<SettingsSidebar />, 260)
    return () => clearSidebar()
  }, [setSidebar, clearSidebar])

  const isDirty =
    prefs !== null &&
    (theme !== prefs.theme || notifications !== prefs.notifications_enabled)

  return (
    <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl space-y-8">

          {/* Theme */}
          <section className="space-y-3">
            <div>
              <h2 className="text-sm font-semibold">Theme</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Choose your preferred appearance.
              </p>
            </div>
            <div className="space-y-2">
              {THEMES.map((t) => (
                <label
                  key={t.value}
                  className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                    theme === t.value ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                  }`}
                >
                  <input
                    type="radio"
                    name="theme"
                    value={t.value}
                    checked={theme === t.value}
                    onChange={() => setTheme(t.value)}
                    className="mt-0.5"
                  />
                  <div>
                    <p className="text-sm font-medium">{t.label}</p>
                    <p className="text-xs text-muted-foreground">{t.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </section>

          <Separator />

          {/* Notifications */}
          <section className="space-y-3">
            <div>
              <h2 className="text-sm font-semibold">Notifications</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Control notification preferences.
              </p>
            </div>
            <label className="flex items-center gap-3 rounded-lg border p-3 cursor-pointer hover:bg-muted/50">
              <input
                type="checkbox"
                checked={notifications}
                onChange={(e) => setNotifications(e.target.checked)}
              />
              <div>
                <p className="text-sm font-medium">Enable Notifications</p>
                <p className="text-xs text-muted-foreground">
                  Receive notifications about document processing and system updates.
                </p>
              </div>
            </label>
          </section>

          {/* Save */}
          {error && <p className="text-sm text-destructive">{error}</p>}

          <Button onClick={handleSave} disabled={!isDirty || saving} className="w-full">
            <Save className="mr-2 h-4 w-4" />
            {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Preferences'}
          </Button>

        </div>
    </div>
  )
}
