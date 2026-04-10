import { FileText, User, Building2 } from 'lucide-react';
import { TextInput } from './shared/TextInput';

export function TextInputStates() {
  return (
    <div 
      className="flex gap-8 p-8 overflow-x-auto" 
      style={{ 
        backgroundColor: '#0B1120',
        minHeight: '100vh'
      }}
    >
      {/* Text Input Variants */}
      <div
        className="flex flex-col gap-6 p-6 rounded-2xl"
        style={{
          width: '400px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45',
          flexShrink: 0
        }}
      >
        <div>
          <div style={{ fontSize: '18px', fontWeight: 600, color: '#F1F5F9', marginBottom: '4px' }}>
            Text Input States
          </div>
          <div style={{ fontSize: '13px', color: '#94A3B8' }}>
            Standard text input with icon
          </div>
        </div>

        {/* State 1: Empty */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            STATE 1: EMPTY
          </div>
          <div
            className="flex items-center gap-2 px-3 rounded-[10px]"
            style={{
              height: '40px',
              backgroundColor: '#162033',
              border: '1px solid #1E2D45',
              boxShadow: 'none'
            }}
          >
            <FileText size={16} style={{ color: '#475569' }} />
            <input
              type="text"
              placeholder="Enter document title"
              className="flex-1 bg-transparent border-none outline-none pointer-events-none"
              style={{
                fontSize: '13px',
                color: '#475569'
              }}
            />
          </div>
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            Border: #1E2D45 • Placeholder visible
          </div>
        </div>

        {/* State 2: Filled */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            STATE 2: FILLED
          </div>
          <div
            className="flex items-center gap-2 px-3 rounded-[10px]"
            style={{
              height: '40px',
              backgroundColor: '#162033',
              border: '1px solid #1E2D45',
              boxShadow: 'none'
            }}
          >
            <User size={16} style={{ color: '#475569' }} />
            <div
              className="flex-1"
              style={{
                fontSize: '13px',
                color: '#F1F5F9'
              }}
            >
              Erik Gunawan
            </div>
          </div>
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            Border: #1E2D45 • Text: #F1F5F9
          </div>
        </div>

        {/* State 3: Focused */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#7C5CFC', letterSpacing: '0.08em' }}>
            STATE 3: FOCUSED
          </div>
          <div
            className="flex items-center gap-2 px-3 rounded-[10px]"
            style={{
              height: '40px',
              backgroundColor: '#162033',
              border: '1px solid rgba(124, 92, 252, 0.4)',
              boxShadow: '0 0 0 3px rgba(124, 92, 252, 0.12)'
            }}
          >
            <Building2 size={16} style={{ color: '#7C5CFC' }} />
            <input
              type="text"
              placeholder="Company name"
              className="flex-1 bg-transparent border-none outline-none pointer-events-none"
              style={{
                fontSize: '13px',
                color: '#475569'
              }}
            />
          </div>
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            Border: rgba(124,92,252,0.4) • Glow: 0 0 0 3px rgba(124,92,252,0.12)
          </div>
        </div>

        {/* Interactive Example */}
        <div className="flex flex-col gap-2 pt-4" style={{ borderTop: '1px solid #1E2D45' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            INTERACTIVE EXAMPLE
          </div>
          <TextInput
            label="Document Title"
            placeholder="Try typing here..."
            icon={FileText}
          />
        </div>
      </div>

      {/* Textarea Variants */}
      <div
        className="flex flex-col gap-6 p-6 rounded-2xl"
        style={{
          width: '400px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45',
          flexShrink: 0
        }}
      >
        <div>
          <div style={{ fontSize: '18px', fontWeight: 600, color: '#F1F5F9', marginBottom: '4px' }}>
            Textarea States
          </div>
          <div style={{ fontSize: '13px', color: '#94A3B8' }}>
            Multi-line text input
          </div>
        </div>

        {/* State 1: Empty */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            STATE 1: EMPTY
          </div>
          <textarea
            placeholder="Brief description of the document"
            rows={3}
            className="px-3 py-2.5 rounded-[10px] bg-transparent outline-none resize-none pointer-events-none"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45',
              boxShadow: 'none',
              fontSize: '13px',
              color: '#475569',
              lineHeight: 1.5
            }}
          />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            Border: #1E2D45 • Placeholder visible
          </div>
        </div>

        {/* State 2: Filled */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            STATE 2: FILLED
          </div>
          <textarea
            value="Perjanjian ini mengatur ketentuan kerahasiaan antara pihak pemberi informasi dan pihak penerima informasi dalam rangka kerja sama bisnis."
            rows={3}
            readOnly
            className="px-3 py-2.5 rounded-[10px] bg-transparent outline-none resize-none pointer-events-none"
            style={{
              backgroundColor: '#162033',
              border: '1px solid #1E2D45',
              boxShadow: 'none',
              fontSize: '13px',
              color: '#F1F5F9',
              lineHeight: 1.5
            }}
          />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            Border: #1E2D45 • Text: #F1F5F9
          </div>
        </div>

        {/* State 3: Focused */}
        <div className="flex flex-col gap-2">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#7C5CFC', letterSpacing: '0.08em' }}>
            STATE 3: FOCUSED
          </div>
          <textarea
            placeholder="Additional notes"
            rows={3}
            className="px-3 py-2.5 rounded-[10px] bg-transparent outline-none resize-none pointer-events-none"
            style={{
              backgroundColor: '#162033',
              border: '1px solid rgba(124, 92, 252, 0.4)',
              boxShadow: '0 0 0 3px rgba(124, 92, 252, 0.12)',
              fontSize: '13px',
              color: '#475569',
              lineHeight: 1.5
            }}
          />
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            Border: rgba(124,92,252,0.4) • Glow: 0 0 0 3px rgba(124,92,252,0.12)
          </div>
        </div>

        {/* Interactive Example */}
        <div className="flex flex-col gap-2 pt-4" style={{ borderTop: '1px solid #1E2D45' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em' }}>
            INTERACTIVE EXAMPLE
          </div>
          <TextInput
            label="Description"
            placeholder="Try typing here..."
            type="textarea"
            rows={4}
          />
        </div>
      </div>

      {/* Combined Usage Example */}
      <div
        className="flex flex-col gap-4 p-6 rounded-2xl"
        style={{
          width: '400px',
          backgroundColor: '#0F1829',
          border: '1px solid #1E2D45',
          flexShrink: 0
        }}
      >
        <div>
          <div style={{ fontSize: '18px', fontWeight: 600, color: '#F1F5F9', marginBottom: '4px' }}>
            Form Example
          </div>
          <div style={{ fontSize: '13px', color: '#94A3B8' }}>
            Mixed input states in context
          </div>
        </div>

        <TextInput
          label="Document Title"
          placeholder="Enter document title"
          icon={FileText}
        />

        <TextInput
          label="Author"
          placeholder="Document author"
          icon={User}
          defaultValue="Erik Gunawan"
        />

        <TextInput
          label="Company"
          placeholder="Company name"
          icon={Building2}
        />

        <TextInput
          label="Description"
          placeholder="Brief description of the document"
          type="textarea"
          rows={3}
        />

        <TextInput
          label="Notes"
          placeholder="Additional notes"
          type="textarea"
          rows={4}
          defaultValue="This document requires review by legal team before finalization. Special attention to clauses 3.2 and 5.1."
        />
      </div>
    </div>
  );
}
