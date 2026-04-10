import { useState } from 'react';
import { FileText, CheckCircle2, XCircle, LucideIcon } from 'lucide-react';

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
  getFileTypeConfig?: (type: string) => { bg: string; color: string };
}

const defaultFileTypeConfig = (type: string) => {
  const configs = {
    pdf: { bg: 'rgba(248, 113, 113, 0.12)', color: '#F87171' },
    docx: { bg: 'rgba(34, 211, 238, 0.12)', color: '#22D3EE' },
    txt: { bg: 'rgba(148, 163, 184, 0.12)', color: '#94A3B8' }
  };
  return configs[type as keyof typeof configs] || configs.pdf;
};

export function DropZone({
  uploadedFile,
  onFileUpload,
  icon: Icon,
  title,
  subtitle,
  browseText = 'browse files',
  formats = 'PDF, DOCX, TXT up to 50MB',
  getFileTypeConfig = defaultFileTypeConfig
}: DropZoneProps) {
  const [hover, setHover] = useState(false);

  if (uploadedFile) {
    const fileConfig = getFileTypeConfig(uploadedFile.type);
    
    return (
      <div
        className="flex items-center gap-3"
        style={{
          height: '80px',
          padding: '0 16px',
          backgroundColor: 'rgba(52, 211, 153, 0.05)',
          border: '1.5px solid rgba(52, 211, 153, 0.35)',
          borderRadius: '14px'
        }}
      >
        <div
          className="flex items-center justify-center"
          style={{
            width: '40px',
            height: '40px',
            borderRadius: '10px',
            backgroundColor: fileConfig.bg,
            flexShrink: 0
          }}
        >
          <FileText size={18} style={{ color: fileConfig.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div
            style={{
              fontSize: '13px',
              fontWeight: 500,
              color: '#F1F5F9',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              marginBottom: '3px'
            }}
          >
            {uploadedFile.name}
          </div>
          <div style={{ fontSize: '11px', color: '#475569' }}>
            {uploadedFile.size} · {uploadedFile.type.toUpperCase()} · Ready
          </div>
        </div>
        <div className="flex items-center gap-2">
          <CheckCircle2 size={16} style={{ color: '#34D399' }} />
          <button
            onClick={() => onFileUpload(null)}
            className="transition-colors duration-150"
            style={{ color: '#475569' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#F87171')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#475569')}
          >
            <XCircle size={14} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex flex-col items-center justify-center transition-all duration-200"
      style={{
        height: '160px',
        backgroundColor: hover ? 'rgba(124, 92, 252, 0.05)' : '#162033',
        border: hover 
          ? '1.5px dashed rgba(124, 92, 252, 0.6)' 
          : '1.5px dashed rgba(100, 116, 139, 0.4)',
        borderRadius: '14px',
        padding: '20px',
        gap: '8px',
        cursor: 'pointer',
        boxShadow: hover ? '0 0 24px rgba(124, 92, 252, 0.12)' : 'none'
      }}
      onDragEnter={() => setHover(true)}
      onDragLeave={() => setHover(false)}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        setHover(false);
        onFileUpload({ 
          name: 'Document.pdf', 
          size: '2.4 MB', 
          type: 'pdf' 
        });
      }}
      onClick={() => onFileUpload({ 
        name: 'Document.pdf', 
        size: '2.4 MB', 
        type: 'pdf' 
      })}
    >
      <div
        className="flex items-center justify-center transition-all duration-200"
        style={{
          width: '44px',
          height: '44px',
          borderRadius: '50%',
          backgroundColor: hover ? 'rgba(124, 92, 252, 0.18)' : 'rgba(124, 92, 252, 0.10)',
          border: '1px solid rgba(124, 92, 252, 0.15)'
        }}
      >
        <Icon size={22} style={{ color: '#7C5CFC' }} />
      </div>
      <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9', textAlign: 'center' }}>
        {title}
      </div>
      <div style={{ fontSize: '12px', color: '#475569', textAlign: 'center' }}>
        {subtitle}{' '}
        <span style={{ color: '#7C5CFC', textDecoration: 'underline' }}>
          {browseText}
        </span>
      </div>
      <div style={{ fontSize: '11px', color: '#475569', textAlign: 'center' }}>
        {formats}
      </div>
    </div>
  );
}
