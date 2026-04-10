import { useState } from 'react';
import { type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TextInputProps {
  label?: string;
  placeholder: string;
  icon?: LucideIcon;
  type?: 'text' | 'textarea';
  rows?: number;
  value?: string;
  onChange?: (value: string) => void;
  defaultValue?: string;
  className?: string;
}

export function TextInput({
  label,
  placeholder,
  icon: Icon,
  type = 'text',
  rows = 3,
  value: controlledValue,
  onChange,
  defaultValue = '',
  className,
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

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      {label && (
        <label className="text-[13px] font-semibold text-slate-100">
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
          className={cn(
            'px-3 py-2.5 rounded-[10px] bg-bg-deep outline-none resize-none transition-all duration-200',
            'border text-[13px] leading-normal',
            isFocused
              ? 'border-accent-primary/40 ring-[3px] ring-accent-primary/[0.12]'
              : 'border-border-subtle',
            isEmpty ? 'text-text-faint' : 'text-slate-100',
          )}
        />
      ) : (
        <div
          className={cn(
            'flex items-center gap-2 px-3 h-10 rounded-[10px] bg-bg-deep transition-all duration-200',
            'border',
            isFocused
              ? 'border-accent-primary/40 ring-[3px] ring-accent-primary/[0.12]'
              : 'border-border-subtle',
          )}
        >
          {Icon && (
            <Icon
              className={cn(
                'size-4 shrink-0 transition-colors duration-200',
                isFocused ? 'text-accent-primary' : 'text-text-faint',
              )}
            />
          )}
          <input
            type="text"
            placeholder={placeholder}
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            className={cn(
              'flex-1 bg-transparent border-none outline-none text-[13px]',
              isEmpty ? 'text-text-faint' : 'text-slate-100',
              'placeholder:text-text-faint',
            )}
          />
        </div>
      )}
    </div>
  );
}
