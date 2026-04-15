import { useState } from 'react'
import { Upload, X, FileText } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'

interface DropZoneProps {
  label?: string
  onFileSelect?: (file: File) => void
}

export function DropZone({ label, onFileSelect }: DropZoneProps) {
  const { t } = useI18n()
  const [file, setFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)

  function handleFile(f: File) {
    setFile(f)
    onFileSelect?.(f)
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (f) handleFile(f)
  }

  if (file) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-green-500/30 bg-green-500/5 p-3">
        <FileText className="h-5 w-5 shrink-0 text-green-600 dark:text-green-400" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{file.name}</p>
          <p className="text-xs text-muted-foreground">{t('shared.dropzone.attached')}</p>
        </div>
        <button
          onClick={() => setFile(null)}
          className="text-muted-foreground hover:text-foreground transition-colors"
          aria-label={t('shared.dropzone.remove')}
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    )
  }

  return (
    <label
      className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 cursor-pointer transition-colors ${
        dragOver ? 'border-primary bg-primary/5 shadow-[var(--glow-sm)]' : 'border-border hover:border-primary/50'
      }`}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
    >
      <input type="file" className="hidden" onChange={handleChange} />
      <Upload className="h-8 w-8 mb-2 text-muted-foreground" />
      <p className="text-sm font-medium">{label ?? t('shared.dropzone.title')}</p>
      <p className="text-xs text-muted-foreground mt-1">{t('shared.dropzone.subtitle')}</p>
    </label>
  )
}
