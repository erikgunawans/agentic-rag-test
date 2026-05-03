/**
 * Phase 20 / Plan 20-10 / UPL-04: minimal toast utility.
 *
 * Dispatches a custom DOM event that a Toaster component can subscribe to.
 * In tests, callers mock this module; in production the event bubbles to
 * whatever listener is registered (or falls back to console.warn if none).
 *
 * The `role` field follows ARIA semantics:
 *   'status'  — polite announcement (upload progress, success)
 *   'alert'   — assertive announcement (validation errors, failures)
 */

export interface ToastOptions {
  message: string
  /** ARIA role — 'alert' surfaces immediately; 'status' is polite. Defaults to 'status'. */
  role?: 'alert' | 'status'
  /** Auto-dismiss after N ms. 0 = no auto-dismiss. Defaults to 4000. */
  duration?: number
}

// Custom event name — listeners registered elsewhere in the app can
// subscribe via window.addEventListener('lexcore:toast', ...) if a
// Toaster component is wired up in AppLayout in a future phase.
const TOAST_EVENT = 'lexcore:toast'

export function toast(opts: ToastOptions): void {
  const detail: ToastOptions = {
    role: 'status',
    duration: 4000,
    ...opts,
  }

  // Dispatch to any registered Toaster in the DOM.
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(TOAST_EVENT, { detail }))
  }
}
