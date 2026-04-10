import { Home, Folder, FilePlus, GitCompare, ShieldCheck, Scale } from 'lucide-react';

export function KnowledgeHubOverview() {
  const pages = [
    {
      id: 1,
      title: 'Chat',
      icon: Home,
      iconName: 'home',
      description: 'Main chat interface',
      thumbnail: '/thumbnails/chat.png',
      color: '#7C5CFC'
    },
    {
      id: 2,
      title: 'Documents',
      icon: Folder,
      iconName: 'folder',
      description: 'Document management',
      thumbnail: '/thumbnails/documents.png',
      color: '#22D3EE'
    },
    {
      id: 3,
      title: 'Create Document',
      icon: FilePlus,
      iconName: 'file-plus',
      description: 'Document creation form',
      thumbnail: '/thumbnails/create.png',
      color: '#7C5CFC'
    },
    {
      id: 4,
      title: 'Compare Documents',
      icon: GitCompare,
      iconName: 'git-compare',
      description: 'Side-by-side comparison',
      thumbnail: '/thumbnails/compare.png',
      color: '#22D3EE'
    },
    {
      id: 5,
      title: 'Compliance Check',
      icon: ShieldCheck,
      iconName: 'shield-check',
      description: 'Regulatory compliance',
      thumbnail: '/thumbnails/compliance.png',
      color: '#34D399'
    },
    {
      id: 6,
      title: 'Contract Analysis',
      icon: Scale,
      iconName: 'scale',
      description: 'Risk & clause analysis',
      thumbnail: '/thumbnails/analysis.png',
      color: '#F59E0B'
    }
  ];

  return (
    <div
      className="flex items-center justify-center"
      style={{
        width: '1440px',
        height: '900px',
        backgroundColor: '#0B1120',
        padding: '40px'
      }}
    >
      {/* Main Container */}
      <div className="flex flex-col gap-8 w-full h-full">
        {/* Header */}
        <div className="flex flex-col items-center gap-3">
          <h1
            style={{
              fontSize: '32px',
              fontWeight: 700,
              color: '#F1F5F9',
              letterSpacing: '-0.02em'
            }}
          >
            Knowledge Hub{' '}
            <span
              style={{
                background: 'linear-gradient(to right, #7C5CFC, #A78BFA, #60A5FA)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text'
              }}
            >
              Navigation Map
            </span>
          </h1>
          <p style={{ fontSize: '14px', color: '#94A3B8' }}>
            Six core page states for legal professionals
          </p>
        </div>

        {/* Grid of Thumbnails */}
        <div
          className="grid gap-6 flex-1"
          style={{
            gridTemplateColumns: 'repeat(3, 1fr)',
            gridTemplateRows: 'repeat(2, 1fr)'
          }}
        >
          {pages.map((page) => {
            const Icon = page.icon;
            return (
              <div
                key={page.id}
                className="flex flex-col rounded-2xl overflow-hidden"
                style={{
                  backgroundColor: '#0F1829',
                  border: '1px solid #1E2D45'
                }}
              >
                {/* Thumbnail Preview */}
                <div
                  className="flex-1 relative flex items-center justify-center overflow-hidden"
                  style={{
                    backgroundColor: '#162033',
                    borderBottom: '1px solid #1E2D45'
                  }}
                >
                  {/* Render actual mini version of each page */}
                  {page.id === 1 && <ChatThumbnail />}
                  {page.id === 2 && <DocumentsThumbnail />}
                  {page.id === 3 && <CreateDocumentThumbnail />}
                  {page.id === 4 && <CompareDocumentsThumbnail />}
                  {page.id === 5 && <ComplianceCheckThumbnail />}
                  {page.id === 6 && <ContractAnalysisThumbnail />}

                  {/* Page Number Badge */}
                  <div
                    className="absolute top-3 left-3 flex items-center justify-center rounded-lg"
                    style={{
                      width: '32px',
                      height: '32px',
                      backgroundColor: 'rgba(11, 17, 32, 0.8)',
                      backdropFilter: 'blur(8px)',
                      border: '1px solid #1E2D45',
                      fontSize: '14px',
                      fontWeight: 700,
                      color: page.color
                    }}
                  >
                    {page.id}
                  </div>
                </div>

                {/* Label Section */}
                <div className="flex items-center gap-3 p-4">
                  <div
                    className="flex items-center justify-center rounded-lg"
                    style={{
                      width: '40px',
                      height: '40px',
                      backgroundColor: `${page.color}15`,
                      border: `1px solid ${page.color}40`
                    }}
                  >
                    <Icon size={20} style={{ color: page.color }} />
                  </div>
                  <div className="flex flex-col gap-0.5 flex-1">
                    <div style={{ fontSize: '14px', fontWeight: 600, color: '#F1F5F9' }}>
                      {page.title}
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748B' }}>
                      Icon: <span style={{ color: page.color, fontFamily: 'monospace' }}>{page.iconName}</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer Legend */}
        <div
          className="flex items-center justify-center gap-8 px-6 py-3 rounded-xl"
          style={{
            backgroundColor: '#0F1829',
            border: '1px solid #1E2D45'
          }}
        >
          <div className="flex items-center gap-2">
            <div
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#7C5CFC'
              }}
            />
            <span style={{ fontSize: '11px', color: '#94A3B8' }}>Creation & Chat</span>
          </div>
          <div className="flex items-center gap-2">
            <div
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#22D3EE'
              }}
            />
            <span style={{ fontSize: '11px', color: '#94A3B8' }}>Management & Comparison</span>
          </div>
          <div className="flex items-center gap-2">
            <div
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#34D399'
              }}
            />
            <span style={{ fontSize: '11px', color: '#94A3B8' }}>Compliance & Validation</span>
          </div>
          <div className="flex items-center gap-2">
            <div
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#F59E0B'
              }}
            />
            <span style={{ fontSize: '11px', color: '#94A3B8' }}>Analysis & Intelligence</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// Thumbnail Components (Scaled down versions)
function ChatThumbnail() {
  return (
    <div
      className="flex w-full h-full"
      style={{
        transform: 'scale(0.18)',
        transformOrigin: 'center center',
        width: '1440px',
        height: '900px'
      }}
    >
      {/* Simplified Chat View */}
      <div style={{ width: '260px', backgroundColor: '#0F1829', borderRight: '1px solid #1E2D45' }} />
      <div className="flex-1 flex items-center justify-center" style={{ backgroundColor: '#0B1120' }}>
        <div className="flex flex-col items-center gap-6">
          <div style={{ fontSize: '80px', fontWeight: 700, color: '#F1F5F9' }}>💬</div>
          <div
            style={{
              width: '600px',
              height: '120px',
              backgroundColor: '#162033',
              border: '1px solid #7C5CFC',
              borderRadius: '20px',
              boxShadow: '0 0 40px rgba(124, 92, 252, 0.3)'
            }}
          />
          <div className="flex gap-4">
            <div
              style={{
                width: '280px',
                height: '60px',
                backgroundColor: '#162033',
                border: '1px solid #1E2D45',
                borderRadius: '16px'
              }}
            />
            <div
              style={{
                width: '280px',
                height: '60px',
                backgroundColor: '#162033',
                border: '1px solid #1E2D45',
                borderRadius: '16px'
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function DocumentsThumbnail() {
  return (
    <div
      className="flex w-full h-full"
      style={{
        transform: 'scale(0.18)',
        transformOrigin: 'center center',
        width: '1440px',
        height: '900px'
      }}
    >
      <div style={{ width: '60px', backgroundColor: '#080C14' }} />
      <div style={{ width: '280px', backgroundColor: '#0F1829', borderRight: '1px solid #1E2D45', padding: '20px' }}>
        <div className="flex flex-col gap-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              style={{
                height: '40px',
                backgroundColor: '#162033',
                border: '1px solid #1E2D45',
                borderRadius: '8px'
              }}
            />
          ))}
        </div>
      </div>
      <div style={{ width: '220px', backgroundColor: '#0F1829', borderRight: '1px solid #1E2D45', padding: '20px' }}>
        <div className="flex flex-col gap-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              style={{
                height: '36px',
                backgroundColor: '#162033',
                border: '1px solid #1E2D45',
                borderRadius: '8px'
              }}
            />
          ))}
        </div>
      </div>
      <div className="flex-1 p-6" style={{ backgroundColor: '#0B1120' }}>
        <div
          className="grid gap-3"
          style={{
            gridTemplateColumns: 'repeat(4, 1fr)',
            gridTemplateRows: 'repeat(3, 1fr)'
          }}
        >
          {[...Array(12)].map((_, i) => (
            <div
              key={i}
              style={{
                backgroundColor: '#162033',
                border: '1px solid #1E2D45',
                borderRadius: '12px',
                minHeight: '140px'
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function CreateDocumentThumbnail() {
  return (
    <div
      className="flex w-full h-full"
      style={{
        transform: 'scale(0.18)',
        transformOrigin: 'center center',
        width: '1440px',
        height: '900px'
      }}
    >
      <div style={{ width: '88px', backgroundColor: '#0B1120' }} />
      <div style={{ width: '360px', backgroundColor: '#0F1829', borderRight: '1px solid #1E2D45', padding: '20px' }}>
        <div className="flex flex-col gap-4">
          <div
            style={{
              height: '50px',
              backgroundColor: '#7C5CFC',
              borderRadius: '12px'
            }}
          />
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              style={{
                height: '60px',
                backgroundColor: '#162033',
                border: '1px solid #1E2D45',
                borderRadius: '10px'
              }}
            />
          ))}
        </div>
      </div>
      <div className="flex-1 flex items-center justify-center p-8" style={{ backgroundColor: '#0B1120' }}>
        <div
          className="flex items-center justify-center"
          style={{
            width: '100%',
            height: '100%',
            backgroundColor: '#0F1829',
            border: '2px dashed #1E2D45',
            borderRadius: '20px',
            fontSize: '60px'
          }}
        >
          📄
        </div>
      </div>
    </div>
  );
}

function CompareDocumentsThumbnail() {
  return (
    <div
      className="flex w-full h-full"
      style={{
        transform: 'scale(0.18)',
        transformOrigin: 'center center',
        width: '1440px',
        height: '900px'
      }}
    >
      <div style={{ width: '88px', backgroundColor: '#0B1120' }} />
      <div style={{ width: '340px', backgroundColor: '#0F1829', borderRight: '1px solid #1E2D45', padding: '20px' }}>
        <div className="flex flex-col gap-4">
          {[1, 2].map((i) => (
            <div
              key={i}
              style={{
                height: '180px',
                backgroundColor: '#162033',
                border: '1px solid #22D3EE',
                borderRadius: '12px',
                boxShadow: '0 0 20px rgba(34, 211, 238, 0.2)'
              }}
            />
          ))}
          <div
            style={{
              height: '50px',
              backgroundColor: '#7C5CFC',
              borderRadius: '12px'
            }}
          />
          <div className="flex flex-col gap-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                style={{
                  height: '44px',
                  backgroundColor: '#162033',
                  border: '1px solid #1E2D45',
                  borderRadius: '8px'
                }}
              />
            ))}
          </div>
        </div>
      </div>
      <div className="flex-1 flex items-center justify-center p-8" style={{ backgroundColor: '#0B1120' }}>
        <div className="grid grid-cols-2 gap-4 w-full h-full">
          <div
            style={{
              backgroundColor: '#0F1829',
              border: '1px solid #1E2D45',
              borderRadius: '16px'
            }}
          />
          <div
            style={{
              backgroundColor: '#0F1829',
              border: '1px solid #1E2D45',
              borderRadius: '16px'
            }}
          />
        </div>
      </div>
    </div>
  );
}

function ComplianceCheckThumbnail() {
  return (
    <div
      className="flex w-full h-full"
      style={{
        transform: 'scale(0.18)',
        transformOrigin: 'center center',
        width: '1440px',
        height: '900px'
      }}
    >
      <div style={{ width: '88px', backgroundColor: '#0B1120' }} />
      <div style={{ width: '320px', backgroundColor: '#0F1829', borderRight: '1px solid #1E2D45', padding: '20px' }}>
        <div className="flex flex-col gap-4">
          <div
            style={{
              height: '160px',
              backgroundColor: '#162033',
              border: '1px solid #34D399',
              borderRadius: '12px',
              boxShadow: '0 0 20px rgba(52, 211, 153, 0.2)'
            }}
          />
          <div
            style={{
              height: '50px',
              backgroundColor: '#34D399',
              borderRadius: '12px'
            }}
          />
          <div className="flex flex-col gap-2">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                style={{
                  height: '44px',
                  backgroundColor: '#162033',
                  border: '1px solid #1E2D45',
                  borderRadius: '8px'
                }}
              />
            ))}
          </div>
        </div>
      </div>
      <div className="flex-1 flex flex-col items-center justify-center gap-6 p-8" style={{ backgroundColor: '#0B1120' }}>
        <div
          className="flex items-center justify-center"
          style={{
            width: '120px',
            height: '120px',
            backgroundColor: 'rgba(52, 211, 153, 0.1)',
            border: '2px solid #34D399',
            borderRadius: '50%',
            fontSize: '60px'
          }}
        >
          ✓
        </div>
        <div className="flex gap-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              style={{
                width: '200px',
                height: '100px',
                backgroundColor: '#162033',
                border: '1px solid #1E2D45',
                borderRadius: '12px'
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function ContractAnalysisThumbnail() {
  return (
    <div
      className="flex w-full h-full"
      style={{
        transform: 'scale(0.18)',
        transformOrigin: 'center center',
        width: '1440px',
        height: '900px'
      }}
    >
      <div style={{ width: '88px', backgroundColor: '#0B1120' }} />
      <div style={{ width: '320px', backgroundColor: '#0F1829', borderRight: '1px solid #1E2D45', padding: '20px' }}>
        <div className="flex flex-col gap-4">
          <div
            style={{
              height: '160px',
              backgroundColor: '#162033',
              border: '1px solid #F59E0B',
              borderRadius: '12px',
              boxShadow: '0 0 20px rgba(245, 158, 11, 0.2)'
            }}
          />
          <div
            style={{
              height: '50px',
              backgroundColor: '#F59E0B',
              borderRadius: '12px'
            }}
          />
          <div className="flex flex-col gap-2">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                style={{
                  height: '44px',
                  backgroundColor: '#162033',
                  border: '1px solid #1E2D45',
                  borderRadius: '8px'
                }}
              />
            ))}
          </div>
        </div>
      </div>
      <div className="flex-1 flex flex-col items-center justify-center gap-6 p-8" style={{ backgroundColor: '#0B1120' }}>
        <div
          className="flex items-center justify-center"
          style={{
            width: '120px',
            height: '120px',
            backgroundColor: 'rgba(245, 158, 11, 0.1)',
            border: '2px solid #F59E0B',
            borderRadius: '50%',
            fontSize: '60px'
          }}
        >
          ⚖️
        </div>
        <div className="flex gap-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              style={{
                width: '200px',
                height: '100px',
                backgroundColor: '#162033',
                border: '1px solid #1E2D45',
                borderRadius: '12px'
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
