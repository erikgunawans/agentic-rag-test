import { useState } from 'react'
import { Folder, FolderOpen, ChevronRight, ChevronDown, Trash2, Home, Globe, Lock } from 'lucide-react'
import type { DocumentFolder } from '@/lib/database.types'

interface FolderTreeProps {
  folders: DocumentFolder[]
  currentFolderId: string | null
  currentUserId: string | null
  onSelectFolder: (folderId: string | null) => void
  onDeleteFolder: (folderId: string) => void
  onToggleGlobal?: (folderId: string) => void
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

/** Check if a node is inside a global subtree (ancestor is global) */
function isInGlobalSubtree(folder: DocumentFolder, folders: DocumentFolder[]): boolean {
  if (folder.is_global) return true
  if (!folder.parent_folder_id) return false
  const parent = folders.find((f) => f.id === folder.parent_folder_id)
  return parent ? isInGlobalSubtree(parent, folders) : false
}

function FolderNode({
  node,
  depth,
  currentFolderId,
  currentUserId,
  allFolders,
  onSelectFolder,
  onDeleteFolder,
  onToggleGlobal,
}: {
  node: TreeNode
  depth: number
  currentFolderId: string | null
  currentUserId: string | null
  allFolders: DocumentFolder[]
  onSelectFolder: (id: string | null) => void
  onDeleteFolder: (id: string) => void
  onToggleGlobal?: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(depth < 2)
  const [showContextMenu, setShowContextMenu] = useState(false)
  const [contextPos, setContextPos] = useState({ x: 0, y: 0 })
  const isActive = currentFolderId === node.folder.id
  const hasChildren = node.children.length > 0
  const isOwner = currentUserId === node.folder.user_id
  const isGlobal = node.folder.is_global
  const isInherited = !isGlobal && isInGlobalSubtree(node.folder, allFolders)
  const isTopLevel = node.folder.parent_folder_id === null
  const isSharedView = !isOwner && (isGlobal || isInherited)

  function handleContextMenu(e: React.MouseEvent) {
    if (!isOwner || !isTopLevel || !onToggleGlobal) return
    e.preventDefault()
    setShowContextMenu(true)
    setContextPos({ x: e.clientX, y: e.clientY })
  }

  return (
    <div>
      <button
        onClick={() => onSelectFolder(node.folder.id)}
        onContextMenu={handleContextMenu}
        onBlur={() => setTimeout(() => setShowContextMenu(false), 150)}
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
        {/* Icon: Globe for global, regular folder otherwise */}
        {isGlobal || isInherited ? (
          <Globe className="h-3.5 w-3.5 shrink-0 text-blue-500" />
        ) : expanded && hasChildren ? (
          <FolderOpen className="h-3.5 w-3.5 shrink-0" />
        ) : (
          <Folder className="h-3.5 w-3.5 shrink-0" />
        )}
        <span className="truncate flex-1 text-left">
          {node.folder.name}
          {isSharedView && (
            <span className="ml-1 text-[10px] text-muted-foreground/60">(shared)</span>
          )}
        </span>
        {/* Only owner can delete */}
        {isOwner && (
          <button
            onClick={(e) => { e.stopPropagation(); onDeleteFolder(node.folder.id) }}
            className="opacity-0 group-hover:opacity-100 shrink-0 p-0.5 text-muted-foreground hover:text-destructive transition-all"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        )}
        {/* Lock icon for non-owners viewing shared folders */}
        {isSharedView && (
          <Lock className="h-3 w-3 shrink-0 text-muted-foreground/40" />
        )}
      </button>

      {/* Context menu for top-level folder sharing */}
      {showContextMenu && (
        <div
          className="fixed z-50 min-w-[180px] rounded-md border border-border bg-popover p-1 shadow-md"
          style={{ left: contextPos.x, top: contextPos.y }}
        >
          <button
            onClick={() => {
              setShowContextMenu(false)
              onToggleGlobal?.(node.folder.id)
            }}
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs hover:bg-muted transition-colors"
          >
            <Globe className="h-3.5 w-3.5" />
            {isGlobal ? 'Make Private' : 'Share with All'}
          </button>
        </div>
      )}

      {expanded && hasChildren && (
        <div>
          {node.children.map((child) => (
            <FolderNode
              key={child.folder.id}
              node={child}
              depth={depth + 1}
              currentFolderId={currentFolderId}
              currentUserId={currentUserId}
              allFolders={allFolders}
              onSelectFolder={onSelectFolder}
              onDeleteFolder={onDeleteFolder}
              onToggleGlobal={onToggleGlobal}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export function FolderTree({ folders, currentFolderId, currentUserId, onSelectFolder, onDeleteFolder, onToggleGlobal }: FolderTreeProps) {
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
          currentUserId={currentUserId}
          allFolders={folders}
          onSelectFolder={onSelectFolder}
          onDeleteFolder={onDeleteFolder}
          onToggleGlobal={onToggleGlobal}
        />
      ))}
    </div>
  )
}
