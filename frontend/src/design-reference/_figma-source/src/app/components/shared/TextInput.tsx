import React, { useState } from 'react';
import { LucideIcon } from 'lucide-react';

interface TextInputProps {
  label?: string;
  placeholder: string;
  icon?: LucideIcon;
  type?: 'text' | 'textarea';
  rows?: number;
  value?: string;
  onChange?: (value: string) => void;
  defaultValue?: string;
}

export function TextInput({
  label,
  placeholder,
  icon: Icon,
  type = 'text',
  rows = 3,
  value: controlledValue,
  onChange,
  defaultValue = ''
}: TextInputProps) {
  const [internalValue, setInternalValue] = useState(defaultValue);
  const [isFocused, setIsFocused] = useState(false);

  const value = controlledValue !== undefined ? controlledValue : internalValue;
  const isEmpty = !value || value.trim() === '';

  const handleChange = (newValue: string) => {
    if (controlledValue === undefined) {
      setInternalValue(newValue);
    }
    onChange?.(newValue);
  };

  // Determine border and shadow based on state
  const getBorderStyle = () => {
    if (isFocused) {
      return {
        border: '1px solid rgba(124, 92, 252, 0.4)',
        boxShadow: '0 0 0 3px rgba(124, 92, 252, 0.12)'
      };
    }
    return {
      border: '1px solid #1E2D45',
      boxShadow: 'none'
    };
  };

  const borderStyle = getBorderStyle();

  return (
    <div className="flex flex-col gap-2">
      {label && (
        <label style={{ fontSize: '13px', fontWeight: 600, color: '#F1F5F9' }}>
          {label}
        </label>
      )}

      {type === 'textarea' ? (
        <textarea
          placeholder={placeholder}
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          rows={rows}
          className="px-3 py-2.5 rounded-[10px] bg-transparent outline-none resize-none transition-all duration-200"
          style={{
            backgroundColor: '#162033',
            ...borderStyle,
            fontSize: '13px',
            color: isEmpty ? '#475569' : '#F1F5F9',
            lineHeight: 1.5
          }}
        />
      ) : (
        <div
          className="flex items-center gap-2 px-3 rounded-[10px] transition-all duration-200"
          style={{
            height: '40px',
            backgroundColor: '#162033',
            ...borderStyle
          }}
        >
          {Icon && (
            <Icon 
              size={16} 
              style={{ 
                color: isFocused ? '#7C5CFC' : '#475569',
                transition: 'color 0.2s'
              }} 
            />
          )}
          <input
            type="text"
            placeholder={placeholder}
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            className="flex-1 bg-transparent border-none outline-none"
            style={{
              fontSize: '13px',
              color: isEmpty ? '#475569' : '#F1F5F9'
            }}
          />
        </div>
      )}
    </div>
  );
}
