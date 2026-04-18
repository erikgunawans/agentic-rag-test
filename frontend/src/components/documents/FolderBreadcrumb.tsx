import { ChevronRight, Home } from 'lucide-react'
import type { DocumentFolder } from '@/lib/database.types'

interface FolderBreadcrumbProps {
  folders: DocumentFolder[]
  currentFolderId: string | null
  onNavigate: (folderId: string | null) => void
}

function buildBreadcrumb(folders: DocumentFolder[], currentId: string | null): DocumentFolder[] {
  if (!currentId) return []
  const map = new Map(folders.map((f) => [f.id, f]))
  const path: DocumentFolder[] = []
  let current = map.get(currentId)
  while (current) {
    path.unshift(current)
    current = current.parent_folder_id ? map.get(current.parent_folder_id) : undefined
  }
  return path
}

export function FolderBreadcrumb({ folders, currentFolderId, onNavigate }: FolderBreadcrumbProps) {
  const path = buildBreadcrumb(folders, currentFolderId)

  return (
    <nav className="flex items-center gap-1 text-xs text-muted-foreground mb-4">
      <button
        onClick={() => onNavigate(null)}
        className="flex items-center gap-1 hover:text-foreground transition-colors focus-ring rounded px-1 py-0.5"
      >
        <Home className="h-3 w-3" />
        <span>Root</span>
      </button>
      {path.map((folder) => (
        <div key={folder.id} className="flex items-center gap-1">
          <ChevronRight className="h-3 w-3 shrink-0" />
          <button
            onClick={() => onNavigate(folder.id)}
            className={`hover:text-foreground transition-colors focus-ring rounded px-1 py-0.5 ${
              folder.id === currentFolderId ? 'text-foreground font-medium' : ''
            }`}
          >
            {folder.name}
          </button>
        </div>
      ))}
    </nav>
  )
}
