import { useState } from 'react'
import { Database, Search, Globe, ChevronDown, ChevronRight, Loader2 } from 'lucide-react'
import type { ToolCallRecord } from '@/lib/database.types'

const TOOL_CONFIG: Record<string, { icon: typeof Database; label: string }> = {
  search_documents: { icon: Search, label: 'Document Search' },
  query_database: { icon: Database, label: 'Database Query' },
  web_search: { icon: Globe, label: 'Web Search' },
}

function getToolSummary(tool: string, input: Record<string, unknown>): string {
  const query = (input.query || input.sql_query || '') as string
  if (tool === 'search_documents') return `Searched documents for "${query}"`
  if (tool === 'query_database') return `Queried database`
  if (tool === 'web_search') return `Searched the web for "${query}"`
  return `Used ${tool}`
}

interface ToolCallCardProps {
  tool: string
  input: Record<string, unknown>
  output?: Record<string, unknown> | string | null
  isLoading?: boolean
}

export function ToolCallCard({ tool, input, output, isLoading }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false)
  const config = TOOL_CONFIG[tool] || { icon: Search, label: tool }
  const Icon = config.icon

  return (
    <div className="border rounded-md text-xs my-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-muted/50 transition-colors"
      >
        {isLoading ? (
          <Loader2 className="h-3.5 w-3.5 text-muted-foreground animate-spin shrink-0" />
        ) : (
          <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        )}
        <span className="text-muted-foreground truncate flex-1">
          {isLoading ? `${config.label}...` : getToolSummary(tool, input)}
        </span>
        {!isLoading && (
          expanded
            ? <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
            : <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
        )}
      </button>

      {expanded && output && (
        <div className="px-3 pb-2 space-y-1.5 border-t">
          {tool === 'query_database' && typeof output === 'object' && 'query' in output && (
            <div className="mt-1.5">
              <span className="text-muted-foreground">SQL: </span>
              <code className="text-[11px] bg-muted px-1 py-0.5 rounded break-all">
                {output.query as string}
              </code>
            </div>
          )}

          {tool === 'web_search' && typeof output === 'object' && 'results' in output && (
            <div className="mt-1.5 space-y-1">
              {(output.results as Array<{ title: string; url: string; content: string }>)?.map((r, i) => (
                <div key={i}>
                  <a
                    href={r.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    {r.title || r.url}
                  </a>
                  {r.content && (
                    <p className="text-muted-foreground line-clamp-2">{r.content}</p>
                  )}
                </div>
              ))}
            </div>
          )}

          {tool === 'search_documents' && typeof output === 'object' && 'count' in output && (
            <div className="mt-1.5 text-muted-foreground">
              Found {output.count as number} relevant chunk{(output.count as number) !== 1 ? 's' : ''}
            </div>
          )}

          {typeof output === 'object' && 'error' in output && output.error && (
            <div className="mt-1.5 text-red-500">Error: {output.error as string}</div>
          )}
        </div>
      )}
    </div>
  )
}

interface ToolCallListProps {
  toolCalls: ToolCallRecord[]
}

export function ToolCallList({ toolCalls }: ToolCallListProps) {
  return (
    <div className="space-y-0.5">
      {toolCalls.map((tc, i) => (
        <ToolCallCard
          key={i}
          tool={tc.tool}
          input={tc.input}
          output={tc.output as Record<string, unknown>}
        />
      ))}
    </div>
  )
}
