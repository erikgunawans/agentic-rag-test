import { useState, useRef } from 'react';
import { FileText, CheckCircle2, XCircle, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface UploadedFile {
  name: string;
  size: string;
  type: string;
}

interface DropZoneProps {
  uploadedFile: UploadedFile | null;
  onFileUpload: (file: UploadedFile | null) => void;
  icon: LucideIcon;
  title: string;
  subtitle: string;
  browseText?: string;
  formats?: string;
  accept?: string;
  getFileTypeConfig?: (type: string) => { bgClass: string; textClass: string };
}

const defaultFileTypeConfig = (type: string): { bgClass: string; textClass: string } => {
  const configs: Record<string, { bgClass: string; textClass: string }> = {
    pdf: { bgClass: 'bg-danger/12', textClass: 'text-danger' },
    docx: { bgClass: 'bg-info/12', textClass: 'text-info' },
    txt: { bgClass: 'bg-slate-400/12', textClass: 'text-slate-400' },
  };
  return configs[type] || configs.pdf;
};

export function DropZone({
  uploadedFile,
  onFileUpload,
  icon: Icon,
  title,
  subtitle,
  browseText = 'browse files',
  formats = 'PDF, DOCX, TXT up to 50MB',
  accept,
  getFileTypeConfig = defaultFileTypeConfig,
}: DropZoneProps) {
  const [hover, setHover] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase() || '';
    const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
    onFileUpload({
      name: file.name,
      size: `${sizeMB} MB`,
      type: ext,
    });
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileSelect(file);
    // Reset so the same file can be re-selected
    e.target.value = '';
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setHover(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFileSelect(file);
  };

  if (uploadedFile) {
    const fileConfig = getFileTypeConfig(uploadedFile.type);

    return (
      <div
        className={cn(
          'flex items-center gap-3 h-20 px-4 rounded-[14px]',
          'bg-success/5 border-[1.5px] border-success/35'
        )}
      >
        <div
          className={cn(
            'flex items-center justify-center w-10 h-10 rounded-[10px] shrink-0',
            fileConfig.bgClass
          )}
        >
          <FileText size={18} className={fileConfig.textClass} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-medium text-slate-100 truncate mb-0.5">
            {uploadedFile.name}
          </div>
          <div className="text-[11px] text-text-faint">
            {uploadedFile.size} &middot; {uploadedFile.type.toUpperCase()} &middot; Ready
          </div>
        </div>
        <div className="flex items-center gap-2">
          <CheckCircle2 size={16} className="text-success" />
          <button
            onClick={() => onFileUpload(null)}
            className="text-text-faint hover:text-danger transition-colors duration-150"
          >
            <XCircle size={14} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept={accept}
        onChange={handleInputChange}
        className="hidden"
      />
      <div
        className={cn(
          'flex flex-col items-center justify-center h-40 rounded-[14px] p-5 gap-2 cursor-pointer',
          'transition-all duration-200',
          hover
            ? 'bg-accent-primary/5 border-[1.5px] border-dashed border-accent-primary/60 shadow-[0_0_24px_rgba(124,92,252,0.12)]'
            : 'bg-bg-elevated border-[1.5px] border-dashed border-slate-500/40'
        )}
        onDragEnter={() => setHover(true)}
        onDragLeave={() => setHover(false)}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <div
          className={cn(
            'flex items-center justify-center w-11 h-11 rounded-full transition-all duration-200',
            'border border-accent-primary/15',
            hover ? 'bg-accent-primary/18' : 'bg-accent-primary/10'
          )}
        >
          <Icon size={22} className="text-accent-primary" />
        </div>
        <div className="text-[13px] font-semibold text-slate-100 text-center">
          {title}
        </div>
        <div className="text-xs text-text-faint text-center">
          {subtitle}{' '}
          <span className="text-accent-primary underline">{browseText}</span>
        </div>
        <div className="text-[11px] text-text-faint text-center">
          {formats}
        </div>
      </div>
    </>
  );
}
