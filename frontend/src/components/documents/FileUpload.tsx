import { useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import { apiFetch } from '@/lib/api'

const ACCEPTED = '.pdf,.txt,.md,.docx,.csv,.html,.htm,.json'
const ACCEPTED_TYPES = new Set([
  'application/pdf',
  'text/plain',
  'text/markdown',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/csv',
  'text/html',
  'application/json',
])

interface FileUploadProps {
  onUploaded: () => void
}

export function FileUpload({ onUploaded }: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)

  async function handleFile(file: File) {
    if (!ACCEPTED_TYPES.has(file.type)) {
      setError('Only PDF, TXT, Markdown, DOCX, CSV, HTML, and JSON files are supported.')
      return
    }
    setError(null)
    setInfo(null)
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await apiFetch('/documents/upload', { method: 'POST', body: form })
      const data = await res.json()
      if (data.duplicate) {
        setInfo(`"${data.filename}" is already uploaded and processed.`)
      } else {
        onUploaded()
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  return (
    <div
      className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        className="hidden"
        onChange={handleChange}
      />
      <Upload className="h-8 w-8 mx-auto mb-3 text-muted-foreground" />
      <p className="text-sm font-medium">
        {uploading ? 'Uploading…' : 'Drop a file or click to upload'}
      </p>
      <p className="text-xs text-muted-foreground mt-1">PDF, TXT, Markdown, DOCX, CSV, HTML, or JSON · Max 50 MB</p>
      {error && <p className="text-xs text-destructive mt-2">{error}</p>}
      {info && <p className="text-xs text-blue-600 mt-2">{info}</p>}
    </div>
  )
}
