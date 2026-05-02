import { useEffect, useState } from 'react'

import type { PublicSettings } from '@/lib/database.types'

/**
 * Phase 12 / CTX-03 / D-P12-06 — module-level-cached fetch of public deployment
 * configuration. The /settings/public endpoint is unauthenticated (D-P12-05),
 * so this hook does NOT use apiFetch (which would inject a Bearer JWT). A single
 * fetch happens per app load; all subsequent hook mounts share the cached result.
 *
 * Cache invalidation: only on full page reload. Backend changes propagate via
 * Railway redeploy + the user's next page load. Frontend redeploys are NOT
 * required (CTX-03 success criterion #5).
 */

const API_BASE_URL = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '').trim()

interface PublicSettingsState {
  contextWindow: number | null
  error: Error | null
}

// Module-level cache: shared across every hook caller for the lifetime of the
// JS bundle. A single in-flight Promise prevents thundering-herd fetches when
// multiple components mount in the same tick.
let cachedState: PublicSettingsState | null = null
let inFlight: Promise<PublicSettingsState> | null = null

async function fetchPublicSettings(): Promise<PublicSettingsState> {
  try {
    const resp = await fetch(`${API_BASE_URL}/settings/public`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      // Explicitly NOT 'Authorization: Bearer ...' — endpoint is unauth.
    })
    if (!resp.ok) {
      return { contextWindow: null, error: new Error(`HTTP ${resp.status}`) }
    }
    const body = (await resp.json()) as PublicSettings
    return { contextWindow: body.context_window, error: null }
  } catch (err) {
    return {
      contextWindow: null,
      error: err instanceof Error ? err : new Error(String(err)),
    }
  }
}

export function usePublicSettings(): PublicSettingsState {
  // Initialize from module-level cache when available — no effect-driven
  // setState needed for the synchronous-cache-hit path.
  const [state, setState] = useState<PublicSettingsState>(
    () => cachedState ?? { contextWindow: null, error: null }
  )

  useEffect(() => {
    // Cold start: fire fetch (or join in-flight Promise) once per app load.
    // The post-fetch setState below is the documented external-system-sync
    // pattern (fetching from a network resource is the external system).
    if (cachedState !== null) {
      // Cache populated by a sibling hook between mount and effect:
      // re-sync our local state. Suppress the rule for this specific
      // synchronization step — a single tick of cascading render is the
      // intended trade-off for the module-level cache invariant.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState(cachedState)
      return
    }
    if (inFlight === null) {
      inFlight = fetchPublicSettings().then((next) => {
        cachedState = next
        return next
      })
    }
    inFlight.then((next) => setState(next))
  }, [])

  return state
}

/**
 * TEST-ONLY: reset the module-level cache between test runs. Production code
 * MUST NOT call this. Vitest test files import this to ensure isolation.
 */
export function _resetPublicSettingsCacheForTests(): void {
  cachedState = null
  inFlight = null
}
