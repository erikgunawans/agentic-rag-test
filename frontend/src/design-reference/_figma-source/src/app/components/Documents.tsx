import { useState } from 'react';
import {
  Clock,
  CloudUpload,
  Search,
  Grid2x2,
  Shield,
  FileSignature,
  BadgeCheck,
  BarChart3,
  Handshake,
  Receipt,
  Folder,
  ChevronDown,
  LayoutGrid,
  List,
  Plus,
  MoreVertical,
  FileText
} from 'lucide-react';

export function Documents() {
  const [activeFilter, setActiveFilter] = useState(0);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [hoveredCard, setHoveredCard] = useState<number | null>(1); // Show first card in hover state by default
  const [dropZoneHover, setDropZoneHover] = useState(false);
  const [checkedStatus, setCheckedStatus] = useState({
    analyzed: true,
    processing: true,
    pending: false
  });

  const filterItems = [
    { id: 0, label: 'All Documents', icon: Grid2x2, count: 47 },
    { id: 1, label: 'NDA', icon: Shield, count: 12 },
    { id: 2, label: 'Kontrak', icon: FileSignature, count: 9 },
    { id: 3, label: 'Kepatuhan', icon: BadgeCheck, count: 8 },
    { id: 4, label: 'Laporan', icon: BarChart3, count: 7 },
    { id: 5, label: 'Perjanjian', icon: Handshake, count: 6 },
    { id: 6, label: 'Invoice', icon: Receipt, count: 3 },
    { id: 7, label: 'Lainnya', icon: Folder, count: 2 }
  ];

  const recentUploads = [
    { name: 'NDA_Template_2026.pdf', size: '2.4 MB', time: 'Just now', type: 'pdf', status: 'uploaded' },
    { name: 'PT_Marina_Contract.docx', size: '845 KB', time: '2h ago', type: 'docx', status: 'uploaded' },
    { name: 'Payment_Terms_Draft.docx', size: '1.2 MB', time: '2d ago', type: 'docx', status: 'processing' }
  ];

  const documents = [
    {
      id: 1,
      title: 'NDA Kerahasiaan — PT Marina Group 2026',
      type: 'pdf',
      category: 'NDA',
      preview: 'Perjanjian ini mengatur ketentuan kerahasiaan antara...',
      modified: '2h ago',
      status: 'analyzed',
      avatars: ['AS', 'EG']
    },
    {
      id: 2,
      title: 'Kontrak Kerjasama Distribusi Q1',
      type: 'docx',
      category: 'Kontrak',
      preview: 'Syarat dan ketentuan distribusi produk berlaku sejak...',
      modified: '5h ago',
      status: 'analyzed',
      avatars: ['EG', 'AS']
    },
    {
      id: 3,
      title: 'Laporan Kepatuhan Regulasi OJK',
      type: 'pdf',
      category: 'Kepatuhan',
      preview: 'Laporan ini mencakup evaluasi kepatuhan terhadap...',
      modified: '1d ago',
      status: 'analyzed',
      avatars: ['AS', 'JD']
    },
    {
      id: 4,
      title: 'Perjanjian Lisensi Software Enterprise',
      type: 'pdf',
      category: 'Perjanjian',
      preview: 'Lisensi penggunaan perangkat lunak diberikan kepada...',
      modified: '1d ago',
      status: 'analyzed',
      avatars: ['EG', 'AS']
    },
    {
      id: 5,
      title: 'Invoice Jasa Konsultasi — Maret 2026',
      type: 'pdf',
      category: 'Invoice',
      preview: 'Tagihan layanan konsultasi hukum periode Maret...',
      modified: '2d ago',
      status: 'processing',
      avatars: ['AS', 'EG']
    },
    {
      id: 6,
      title: 'Addendum Kontrak Sewa Gedung',
      type: 'docx',
      category: 'Kontrak',
      preview: 'Perubahan klausul sewa sebagaimana tertuang dalam...',
      modified: '2d ago',
      status: 'analyzed',
      avatars: ['JD', 'EG']
    },
    {
      id: 7,
      title: 'Draft NDA — Proyek Ekspansi Regional',
      type: 'docx',
      category: 'NDA',
      preview: 'Rancangan awal perjanjian kerahasiaan untuk proyek...',
      modified: '3d ago',
      status: 'processing',
      avatars: ['AS', 'EG']
    },
    {
      id: 8,
      title: 'Compliance Checklist Q1 2026',
      type: 'docx',
      category: 'Kepatuhan',
      preview: 'Daftar pengecekan kepatuhan untuk kuartal pertama...',
      modified: '3d ago',
      status: 'analyzed',
      avatars: ['EG', 'AS']
    }
  ];

  const getFileTypeBadge = (type: string) => {
    const configs = {
      pdf: { bg: 'rgba(248, 113, 113, 0.12)', color: '#F87171', label: 'PDF' },
      docx: { bg: 'rgba(34, 211, 238, 0.12)', color: '#22D3EE', label: 'DOCX' }
    };
    return configs[type as keyof typeof configs] || configs.pdf;
  };

  const getStatusConfig = (status: string) => {
    const configs = {
      analyzed: { bg: 'rgba(52, 211, 153, 0.1)', border: 'rgba(52, 211, 153, 0.3)', color: '#34D399', label: 'Analyzed' },
      processing: { bg: 'rgba(245, 158, 11, 0.1)', border: 'rgba(245, 158, 11, 0.3)', color: '#F59E0B', label: 'Processing' }
    };
    return configs[status as keyof typeof configs] || configs.analyzed;
  };

  return (
    <>
      {/* Column 2 - Upload + Filter Panel */}
      <div
        className="flex flex-col"
        style={{
          width: '300px',
          backgroundColor: '#0F1829',
          borderRight: '1px solid #1E2D45'
        }}
      >
        {/* SECTION 1: UPLOAD */}
        <div>
          {/* Header */}
          <div
            className="flex items-center justify-between px-5"
            style={{ height: '64px' }}
          >
            <div style={{ fontSize: '15px', fontWeight: 600, color: '#F1F5F9' }}>
              Documents
            </div>
            <button
              className="flex items-center justify-center rounded-lg transition-colors duration-200"
              style={{
                width: '28px',
                height: '28px',
                color: '#94A3B8'
              }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#1C2840')}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              <Clock size={16} />
            </button>
          </div>

          {/* Drop Zone */}
          <div className="mx-4 mb-3">
            <div
              className="flex flex-col items-center justify-center p-5 rounded-2xl transition-all duration-200"
              style={{
                backgroundColor: dropZoneHover ? 'rgba(124, 92, 252, 0.05)' : '#162033',
                border: dropZoneHover ? '2px dashed rgba(124, 92, 252, 0.7)' : '2px dashed rgba(124, 92, 252, 0.35)',
                backgroundImage: 'radial-gradient(circle at center, rgba(124, 92, 252, 0.06) 0%, transparent 70%)'
              }}
              onDragEnter={() => setDropZoneHover(true)}
              onDragLeave={() => setDropZoneHover(false)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                setDropZoneHover(false);
              }}
            >
              <div
                className="flex items-center justify-center rounded-full mb-2"
                style={{
                  width: '40px',
                  height: '40px',
                  backgroundColor: 'rgba(124, 92, 252, 0.1)'
                }}
              >
                <CloudUpload size={22} style={{ color: '#7C5CFC' }} />
              </div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9', marginBottom: '4px' }}>
                Drag & drop files here
              </div>
              <div style={{ fontSize: '11px', color: '#475569', marginBottom: '8px' }}>
                PDF, DOCX, XLSX up to 50MB
              </div>

              {/* Divider */}
              <div className="flex items-center w-full gap-2 my-2">
                <div className="flex-1" style={{ height: '1px', backgroundColor: '#1E2D45' }} />
                <span style={{ fontSize: '11px', color: '#475569' }}>or</span>
                <div className="flex-1" style={{ height: '1px', backgroundColor: '#1E2D45' }} />
              </div>

              <button
                className="flex items-center justify-center rounded-[10px] transition-all duration-200"
                style={{
                  width: '130px',
                  height: '34px',
                  backgroundColor: '#7C5CFC',
                  fontSize: '13px',
                  fontWeight: 600,
                  color: 'white'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#8B6EFD';
                  e.currentTarget.style.boxShadow = '0 4px 16px rgba(124, 92, 252, 0.4)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#7C5CFC';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                Browse Files
              </button>
            </div>
          </div>

          {/* Recent Uploads Label */}
          <div
            className="px-5 py-2"
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: '#475569',
              letterSpacing: '0.08em'
            }}
          >
            RECENT UPLOADS
          </div>

          {/* Recent Upload List */}
          <div>
            {recentUploads.map((file, idx) => {
              const badge = getFileTypeBadge(file.type);
              return (
                <button
                  key={idx}
                  className="w-full flex items-center gap-2.5 px-4 transition-colors duration-150"
                  style={{ height: '52px' }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#1C2840')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <div
                    className="flex items-center justify-center rounded-lg"
                    style={{
                      width: '30px',
                      height: '30px',
                      backgroundColor: badge.bg
                    }}
                  >
                    <FileText size={14} style={{ color: badge.color }} />
                  </div>
                  <div className="flex-1 flex flex-col gap-0.5 items-start min-w-0">
                    <div
                      className="truncate"
                      style={{
                        fontSize: '12px',
                        fontWeight: 500,
                        color: '#F1F5F9',
                        maxWidth: '170px'
                      }}
                    >
                      {file.name}
                    </div>
                    <div style={{ fontSize: '11px', color: '#475569' }}>
                      {file.size} · {file.time}
                    </div>
                  </div>
                  <div
                    className={file.status === 'processing' ? 'animate-pulse' : ''}
                    style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      backgroundColor: file.status === 'uploaded' ? '#34D399' : '#F59E0B',
                      flexShrink: 0
                    }}
                  />
                </button>
              );
            })}
          </div>

          {/* Storage Quota */}
          <div className="flex flex-col gap-1.5 px-4 pt-3 pb-4">
            <div className="flex items-center justify-between">
              <span style={{ fontSize: '12px', color: '#94A3B8' }}>Storage used</span>
              <span style={{ fontSize: '12px', fontWeight: 600, color: '#F1F5F9' }}>2.4 GB / 10 GB</span>
            </div>
            <div
              className="w-full rounded-sm overflow-hidden"
              style={{ height: '4px', backgroundColor: '#1C2840' }}
            >
              <div
                style={{
                  width: '24%',
                  height: '100%',
                  background: 'linear-gradient(to right, #7C5CFC, #A78BFA, #60A5FA)',
                  borderRadius: '2px'
                }}
              />
            </div>
          </div>
        </div>

        {/* Divider */}
        <div style={{ width: '100%', height: '1px', backgroundColor: '#1E2D45' }} />

        {/* SECTION 2: FILTER */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Header */}
          <div
            className="flex items-center justify-between px-5"
            style={{ height: '52px' }}
          >
            <div style={{ fontSize: '15px', fontWeight: 600, color: '#F1F5F9' }}>
              Filter
            </div>
            <button
              className="transition-colors duration-200"
              style={{ fontSize: '12px', color: '#94A3B8' }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#F1F5F9')}
              onMouseLeave={(e) => (e.currentTarget.style.color = '#94A3B8')}
            >
              Reset
            </button>
          </div>

          {/* Search */}
          <div className="px-3 pb-2.5">
            <div
              className="flex items-center gap-2 px-2.5 rounded-[10px]"
              style={{
                height: '32px',
                backgroundColor: '#162033',
                border: '1px solid #1E2D45'
              }}
            >
              <Search size={14} style={{ color: '#475569' }} />
              <input
                type="text"
                placeholder="Search types..."
                className="flex-1 bg-transparent border-none outline-none"
                style={{ fontSize: '12px', color: '#F1F5F9' }}
              />
            </div>
          </div>

          {/* Document Type Label */}
          <div
            className="px-5 py-1"
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: '#475569',
              letterSpacing: '0.08em'
            }}
          >
            DOCUMENT TYPE
          </div>

          {/* Type Filter List */}
          <div className="flex flex-col gap-0.5 px-1.5 py-1.5">
            {filterItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeFilter === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveFilter(item.id)}
                  className="flex items-center gap-2 px-3 rounded-[10px] transition-all duration-150 relative"
                  style={{
                    height: '36px',
                    backgroundColor: isActive ? 'rgba(124, 92, 252, 0.12)' : 'transparent'
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) e.currentTarget.style.backgroundColor = '#1C2840';
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                >
                  {isActive && (
                    <div
                      style={{
                        position: 'absolute',
                        left: '0px',
                        width: '3px',
                        height: '20px',
                        backgroundColor: '#7C5CFC',
                        borderRadius: '2px'
                      }}
                    />
                  )}
                  <Icon
                    size={16}
                    style={{
                      color: isActive ? '#7C5CFC' : '#475569',
                      marginLeft: isActive ? '8px' : '0'
                    }}
                  />
                  <span
                    className="flex-1 text-left"
                    style={{
                      fontSize: '13px',
                      fontWeight: isActive ? 600 : 500,
                      color: isActive ? '#7C5CFC' : '#94A3B8'
                    }}
                  >
                    {item.label}
                  </span>
                  <div
                    className="px-2 rounded-full"
                    style={{
                      height: '20px',
                      display: 'flex',
                      alignItems: 'center',
                      backgroundColor: isActive ? 'rgba(124, 92, 252, 0.2)' : '#162033',
                      fontSize: '11px',
                      color: isActive ? '#7C5CFC' : '#475569'
                    }}
                  >
                    {item.count}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Status Label */}
          <div
            className="px-5 py-1 mt-3"
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: '#475569',
              letterSpacing: '0.08em'
            }}
          >
            STATUS
          </div>

          {/* Status Checkboxes */}
          <div className="flex flex-col gap-0.5 px-4 py-1.5">
            {[
              { key: 'analyzed', label: 'Analyzed', color: '#34D399', count: '38' },
              { key: 'processing', label: 'Processing', color: '#F59E0B', count: '6' },
              { key: 'pending', label: 'Pending', color: '#475569', count: '3' }
            ].map((status) => (
              <button
                key={status.key}
                onClick={() =>
                  setCheckedStatus({
                    ...checkedStatus,
                    [status.key]: !checkedStatus[status.key as keyof typeof checkedStatus]
                  })
                }
                className="flex items-center gap-2.5"
                style={{ height: '32px' }}
              >
                <div
                  className="flex items-center justify-center rounded transition-all duration-150"
                  style={{
                    width: '16px',
                    height: '16px',
                    backgroundColor: checkedStatus[status.key as keyof typeof checkedStatus]
                      ? '#7C5CFC'
                      : 'transparent',
                    border: checkedStatus[status.key as keyof typeof checkedStatus]
                      ? 'none'
                      : '1.5px solid #475569'
                  }}
                >
                  {checkedStatus[status.key as keyof typeof checkedStatus] && (
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                      <path
                        d="M8 2.5L4 7.5L2 5.5"
                        stroke="white"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </div>
                <span style={{ fontSize: '13px', fontWeight: 500, color: '#F1F5F9' }}>
                  {status.label}
                </span>
                <div
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: status.color
                  }}
                />
                <span style={{ fontSize: '11px', color: '#475569', marginLeft: 'auto' }}>
                  {status.count}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Column 3 - Main Document Area */}
      <div className="flex-1 flex flex-col relative overflow-hidden" style={{ backgroundColor: '#0B1120' }}>
        {/* Mesh gradients */}
        <div
          className="absolute top-0 right-0 pointer-events-none"
          style={{
            width: '600px',
            height: '600px',
            background: 'radial-gradient(circle, rgba(76, 29, 149, 0.06) 0%, transparent 70%)'
          }}
        />
        <div
          className="absolute bottom-0 left-0 pointer-events-none"
          style={{
            width: '500px',
            height: '500px',
            background: 'radial-gradient(circle, rgba(10, 31, 61, 0.3) 0%, transparent 70%)'
          }}
        />

        {/* Top Bar */}
        <div
          className="flex items-center justify-between px-6 relative z-10"
          style={{
            height: '64px',
            borderBottom: '1px solid #1E2D45'
          }}
        >
          <div className="flex items-center gap-2">
            <div style={{ fontSize: '20px', fontWeight: 600, color: '#F1F5F9' }}>
              All Documents
            </div>
            <div style={{ fontSize: '13px', color: '#475569' }}>47 documents</div>
          </div>

          <div className="flex items-center gap-2">
            {/* Search Bar */}
            <div
              className="flex items-center gap-2 px-3 rounded-[10px] transition-all duration-200"
              style={{
                width: '240px',
                height: '36px',
                backgroundColor: '#162033',
                border: '1px solid #1E2D45'
              }}
            >
              <Search size={14} style={{ color: '#475569' }} />
              <input
                type="text"
                placeholder="Search documents..."
                className="flex-1 bg-transparent border-none outline-none placeholder:text-[#475569]"
                style={{ fontSize: '13px', color: '#F1F5F9' }}
                onFocus={(e) => {
                  e.currentTarget.parentElement!.style.borderColor = 'rgba(124, 92, 252, 0.4)';
                  e.currentTarget.parentElement!.style.boxShadow = '0 0 0 3px rgba(124, 92, 252, 0.15)';
                }}
                onBlur={(e) => {
                  e.currentTarget.parentElement!.style.borderColor = '#1E2D45';
                  e.currentTarget.parentElement!.style.boxShadow = 'none';
                }}
              />
            </div>

            {/* Sort Dropdown */}
            <button
              className="flex items-center gap-2 px-3 rounded-[10px] transition-colors duration-150"
              style={{
                height: '36px',
                backgroundColor: '#162033',
                border: '1px solid #1E2D45'
              }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#1C2840')}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#162033')}
            >
              <span style={{ fontSize: '13px', color: '#94A3B8' }}>Modified date</span>
              <ChevronDown size={14} style={{ color: '#94A3B8' }} />
            </button>

            {/* View Toggle */}
            <div className="flex" style={{ border: '1px solid #1E2D45', borderRadius: '10px' }}>
              <button
                onClick={() => setViewMode('grid')}
                className="flex items-center justify-center transition-all duration-150"
                style={{
                  width: '36px',
                  height: '36px',
                  backgroundColor: viewMode === 'grid' ? 'rgba(124, 92, 252, 0.15)' : 'transparent',
                  borderRadius: '10px 0 0 10px',
                  color: viewMode === 'grid' ? '#7C5CFC' : '#475569'
                }}
              >
                <LayoutGrid size={16} />
              </button>
              <div style={{ width: '1px', backgroundColor: '#1E2D45' }} />
              <button
                onClick={() => setViewMode('list')}
                className="flex items-center justify-center transition-all duration-150"
                style={{
                  width: '36px',
                  height: '36px',
                  backgroundColor: viewMode === 'list' ? 'rgba(124, 92, 252, 0.15)' : 'transparent',
                  borderRadius: '0 10px 10px 0',
                  color: viewMode === 'list' ? '#7C5CFC' : '#475569'
                }}
              >
                <List size={16} />
              </button>
            </div>

            {/* New Document Button */}
            <button
              className="flex items-center gap-2 px-4 rounded-[10px] transition-all duration-200"
              style={{
                height: '36px',
                backgroundColor: '#7C5CFC',
                fontSize: '13px',
                fontWeight: 600,
                color: 'white'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#8B6EFD';
                e.currentTarget.style.boxShadow = '0 4px 16px rgba(124, 92, 252, 0.3)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#7C5CFC';
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              <Plus size={16} />
              New Document
            </button>
          </div>
        </div>

        {/* Document Grid */}
        <div className="flex-1 overflow-y-auto p-6 relative z-10 documents-grid-scroll" style={{ backgroundColor: '#0B1120' }}>
          <style>
            {`
              .documents-grid-scroll::-webkit-scrollbar {
                width: 4px;
              }
              .documents-grid-scroll::-webkit-scrollbar-track {
                background: transparent;
              }
              .documents-grid-scroll::-webkit-scrollbar-thumb {
                background: rgba(124, 92, 252, 0.25);
                border-radius: 4px;
              }
              .documents-grid-scroll::-webkit-scrollbar-thumb:hover {
                background: rgba(124, 92, 252, 0.45);
              }
            `}
          </style>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: '16px'
            }}
          >
            {documents.map((doc) => {
              const badge = getFileTypeBadge(doc.type);
              const statusConfig = getStatusConfig(doc.status);
              const isHovered = hoveredCard === doc.id;

              return (
                <div
                  key={doc.id}
                  className="flex flex-col rounded-2xl transition-all duration-200 overflow-hidden"
                  style={{
                    height: '180px',
                    backgroundColor: '#162033',
                    border: isHovered ? '1px solid rgba(124, 92, 252, 0.4)' : '1px solid #1E2D45',
                    boxShadow: isHovered ? '0 8px 32px rgba(0, 0, 0, 0.3)' : 'none'
                  }}
                  onMouseEnter={() => setHoveredCard(doc.id)}
                  onMouseLeave={() => setHoveredCard(null)}
                >
                  {/* Top accent line on hover */}
                  {isHovered && (
                    <div
                      style={{
                        height: '3px',
                        background: 'linear-gradient(to right, #7C5CFC, #A78BFA, #60A5FA)'
                      }}
                    />
                  )}

                  <div className="flex flex-col p-4 gap-3 flex-1">
                    {/* Top Row */}
                    <div className="flex items-center justify-between">
                      <div
                        className="flex items-center gap-1.5 px-2.5 rounded-full"
                        style={{
                          height: '26px',
                          backgroundColor: badge.bg
                        }}
                      >
                        <FileText size={12} style={{ color: badge.color }} />
                        <span style={{ fontSize: '11px', fontWeight: 600, color: badge.color }}>
                          {badge.label}
                        </span>
                      </div>
                      <button
                        className="flex items-center justify-center rounded-lg transition-colors duration-150"
                        style={{
                          width: '28px',
                          height: '28px',
                          color: '#94A3B8'
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#1C2840')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        <MoreVertical size={16} />
                      </button>
                    </div>

                    {/* Middle */}
                    <div className="flex flex-col gap-1.5 flex-1">
                      <div
                        style={{
                          fontSize: '14px',
                          fontWeight: 600,
                          color: '#F1F5F9',
                          lineHeight: 1.4,
                          overflow: 'hidden',
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical'
                        }}
                      >
                        {doc.title}
                      </div>
                      <div style={{ fontSize: '11px', color: '#475569' }}>{doc.category}</div>
                      <div
                        style={{
                          fontSize: '12px',
                          color: '#475569',
                          lineHeight: 1.5,
                          overflow: 'hidden',
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical'
                        }}
                      >
                        {doc.preview}
                      </div>
                    </div>

                    {/* Bottom Row */}
                    <div
                      className="flex items-center justify-between pt-2"
                      style={{ borderTop: '1px solid #1E2D45' }}
                    >
                      <div className="flex items-center" style={{ marginLeft: '-4px' }}>
                        {doc.avatars.map((avatar, idx) => (
                          <div
                            key={idx}
                            className="flex items-center justify-center rounded-full"
                            style={{
                              width: '20px',
                              height: '20px',
                              backgroundColor: idx === 0 ? '#7C5CFC' : '#22D3EE',
                              fontSize: '9px',
                              fontWeight: 600,
                              color: 'white',
                              marginLeft: idx > 0 ? '-6px' : '0',
                              border: '2px solid #162033',
                              zIndex: 10 - idx
                            }}
                          >
                            {avatar}
                          </div>
                        ))}
                      </div>
                      <div style={{ fontSize: '11px', color: '#475569' }}>Modified {doc.modified}</div>
                      <div
                        className="px-2 rounded-full"
                        style={{
                          height: '22px',
                          display: 'flex',
                          alignItems: 'center',
                          backgroundColor: statusConfig.bg,
                          border: `1px solid ${statusConfig.border}`,
                          fontSize: '10px',
                          fontWeight: 600,
                          color: statusConfig.color
                        }}
                      >
                        {statusConfig.label}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Ghost card */}
            <button
              className="flex flex-col items-center justify-center rounded-2xl transition-all duration-200"
              style={{
                height: '180px',
                backgroundColor: 'transparent',
                border: '2px dashed #1E2D45'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'rgba(124, 92, 252, 0.4)';
                e.currentTarget.style.backgroundColor = 'rgba(124, 92, 252, 0.03)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#1E2D45';
                e.currentTarget.style.backgroundColor = 'transparent';
              }}
            >
              <Plus size={24} style={{ color: '#475569', marginBottom: '8px' }} />
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#475569' }}>Upload New</div>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}