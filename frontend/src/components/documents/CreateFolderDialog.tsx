import { useState } from 'react'
import { FolderPlus, X } from 'lucide-react'

interface CreateFolderDialogProps {
  open: boolean
  onClose: () => void
  onCreate: (name: string) => Promise<void>
}

export function CreateFolderDialog({ open, onClose, onCreate }: CreateFolderDialogProps) {
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!open) return null

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    setLoading(true)
    setError(null)
    try {
      await onCreate(trimmed)
      setName('')
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create folder')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50" />
      <div
        className="relative w-full max-w-sm rounded-xl border border-border bg-background p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <FolderPlus className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold">New Folder</h3>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Folder name..."
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            className="w-full rounded-lg bg-secondary px-3 py-2 text-xs border border-border focus:outline-none focus:border-primary/50 transition-colors"
          />
          {error && <p className="text-xs text-destructive mt-2">{error}</p>}
          <div className="flex justify-end gap-2 mt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || loading}
              className="rounded-lg bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {loading ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
