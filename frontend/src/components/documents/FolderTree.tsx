import { useState } from 'react'
import { Folder, FolderOpen, ChevronRight, ChevronDown, Trash2, Home } from 'lucide-react'
import type { DocumentFolder } from '@/lib/database.types'

interface FolderTreeProps {
  folders: DocumentFolder[]
  currentFolderId: string | null
  onSelectFolder: (folderId: string | null) => void
  onDeleteFolder: (folderId: string) => void
}

interface TreeNode {
  folder: DocumentFolder
  children: TreeNode[]
}

function buildTree(folders: DocumentFolder[]): TreeNode[] {
  const map = new Map<string, TreeNode>()
  const roots: TreeNode[] = []

  for (const f of folders) {
    map.set(f.id, { folder: f, children: [] })
  }

  for (const f of folders) {
    const node = map.get(f.id)!
    if (f.parent_folder_id && map.has(f.parent_folder_id)) {
      map.get(f.parent_folder_id)!.children.push(node)
    } else {
      roots.push(node)
    }
  }

  // Sort children alphabetically
  const sortChildren = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => a.folder.name.localeCompare(b.folder.name))
    nodes.forEach((n) => sortChildren(n.children))
  }
  sortChildren(roots)

  return roots
}

function FolderNode({
  node,
  depth,
  currentFolderId,
  onSelectFolder,
  onDeleteFolder,
}: {
  node: TreeNode
  depth: number
  currentFolderId: string | null
  onSelectFolder: (id: string | null) => void
  onDeleteFolder: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(depth < 2)
  const isActive = currentFolderId === node.folder.id
  const hasChildren = node.children.length > 0

  return (
    <div>
      <button
        onClick={() => onSelectFolder(node.folder.id)}
        className={`group flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-xs transition-colors focus-ring ${
          isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {hasChildren ? (
          <button
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}
            className="shrink-0 p-0.5 hover:bg-muted rounded"
          >
            {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          </button>
        ) : (
          <span className="w-4" />
        )}
        {expanded && hasChildren ? (
          <FolderOpen className="h-3.5 w-3.5 shrink-0" />
        ) : (
          <Folder className="h-3.5 w-3.5 shrink-0" />
        )}
        <span className="truncate flex-1 text-left">{node.folder.name}</span>
        <button
          onClick={(e) => { e.stopPropagation(); onDeleteFolder(node.folder.id) }}
          className="opacity-0 group-hover:opacity-100 shrink-0 p-0.5 text-muted-foreground hover:text-destructive transition-all"
        >
          <Trash2 className="h-3 w-3" />
        </button>
      </button>
      {expanded && hasChildren && (
        <div>
          {node.children.map((child) => (
            <FolderNode
              key={child.folder.id}
              node={child}
              depth={depth + 1}
              currentFolderId={currentFolderId}
              onSelectFolder={onSelectFolder}
              onDeleteFolder={onDeleteFolder}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export function FolderTree({ folders, currentFolderId, onSelectFolder, onDeleteFolder }: FolderTreeProps) {
  const tree = buildTree(folders)

  return (
    <div className="space-y-0.5">
      {/* Root item */}
      <button
        onClick={() => onSelectFolder(null)}
        className={`flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-xs transition-colors focus-ring ${
          currentFolderId === null ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
        }`}
      >
        <Home className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate flex-1 text-left">All Documents</span>
      </button>

      {tree.map((node) => (
        <FolderNode
          key={node.folder.id}
          node={node}
          depth={0}
          currentFolderId={currentFolderId}
          onSelectFolder={onSelectFolder}
          onDeleteFolder={onDeleteFolder}
        />
      ))}
    </div>
  )
}
