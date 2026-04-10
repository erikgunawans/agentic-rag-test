import { useState, useRef, useEffect } from 'react';
import {
  type LucideIcon,
  Sparkles,
  LayoutGrid,
  X,
  BarChart3,
  Users,
  Bell,
  Settings,
} from 'lucide-react';
import { cn } from '@/lib/utils';

export interface GroupItem {
  id: string;
  icon: LucideIcon;
  label: string;
  isActive?: boolean;
}

export interface IconRailNewProps {
  mainIcons: Array<{
    icon: LucideIcon;
    id: string;
    isActive: boolean;
    onClick: () => void;
  }>;
  groupItems?: GroupItem[];
  activeGroupItemId?: string | null;
  onGroupItemClick?: (id: string) => void;
  userInitials?: string;
  userOnline?: boolean;
}

export function IconRailNew({
  mainIcons,
  groupItems = [
    { id: 'analytics', icon: BarChart3, label: 'Analytics' },
    { id: 'team', icon: Users, label: 'Team Access' },
    { id: 'notifications', icon: Bell, label: 'Notifications' },
    { id: 'settings', icon: Settings, label: 'Settings' },
  ],
  activeGroupItemId = null,
  onGroupItemClick,
  userInitials = 'AS',
  userOnline = true,
}: IconRailNewProps) {
  const [isGroupOpen, setIsGroupOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Close panel when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        isGroupOpen &&
        panelRef.current &&
        triggerRef.current &&
        !panelRef.current.contains(event.target as Node) &&
        !triggerRef.current.contains(event.target as Node)
      ) {
        setIsGroupOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isGroupOpen]);

  const hasActiveSubPage = !!activeGroupItemId;
  const groupTriggerState = isGroupOpen
    ? 'expanded'
    : hasActiveSubPage
      ? 'sub-active'
      : 'collapsed';

  return (
    <div className="relative flex items-center justify-center w-[60px]">
      {/* Icon Rail Container */}
      <div
        className={cn(
          'flex flex-col items-center gap-1.5 py-3 w-14 rounded-[28px]',
          'bg-bg-surface/70 backdrop-blur-xl',
          'border border-border-subtle',
          'shadow-[0_8px_32px_rgba(0,0,0,0.4)]'
        )}
      >
        {/* Logo */}
        <div
          className={cn(
            'flex items-center justify-center w-10 h-10 rounded-lg',
            'bg-accent-primary shadow-[0_0_16px_rgba(124,92,252,0.5)]',
            'transition-all duration-200'
          )}
        >
          <Sparkles size={28} className="text-white" />
        </div>

        {/* Main Navigation Icons */}
        <div className="flex flex-col items-center gap-1.5 mt-1">
          {mainIcons.map(({ icon: Icon, id, isActive, onClick }) => (
            <button
              key={id}
              onClick={onClick}
              className={cn(
                'flex items-center justify-center w-9 h-9 rounded-lg transition-all duration-200',
                isActive
                  ? 'bg-accent-primary/12 text-accent-primary shadow-[0_0_16px_rgba(124,92,252,0.3)]'
                  : 'text-slate-400 hover:bg-bg-hover hover:text-slate-100'
              )}
            >
              <Icon size={20} />
            </button>
          ))}
        </div>

        {/* Divider */}
        <div className="my-1 w-5 h-px bg-border-subtle" />

        {/* Group Trigger Icon */}
        <button
          ref={triggerRef}
          onClick={() => setIsGroupOpen(!isGroupOpen)}
          className={cn(
            'relative flex items-center justify-center w-9 h-9 rounded-lg transition-all duration-200',
            groupTriggerState === 'expanded' &&
              'bg-accent-primary/12 text-accent-primary shadow-[0_0_16px_rgba(124,92,252,0.3)]',
            groupTriggerState === 'sub-active' &&
              'bg-accent-primary/8 text-accent-primary',
            groupTriggerState === 'collapsed' &&
              'text-slate-400 hover:bg-bg-hover hover:text-slate-100'
          )}
        >
          <LayoutGrid size={20} />
          {/* Indicator dot for expanded state */}
          {groupTriggerState === 'expanded' && (
            <div className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-accent-primary" />
          )}
        </button>

        {/* Spacer */}
        <div className="flex-grow min-h-[20px]" />

        {/* User Avatar */}
        <div className="relative">
          <div
            className={cn(
              'flex items-center justify-center w-9 h-9 rounded-full',
              'bg-accent-primary text-white text-[13px] font-semibold'
            )}
          >
            {userInitials}
          </div>
          {/* Presence dot */}
          {userOnline && (
            <div
              className={cn(
                'absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full',
                'bg-success border-2 border-bg-surface/70'
              )}
            />
          )}
        </div>
      </div>

      {/* Group Flyout Panel */}
      {isGroupOpen && (
        <div
          ref={panelRef}
          className={cn(
            'absolute left-[70px] z-[100] flex flex-col w-[220px] p-2',
            'bg-bg-surface/[0.92] backdrop-blur-xl',
            'border border-border-subtle rounded-2xl',
            'shadow-[0_8px_40px_rgba(0,0,0,0.5),0_0_0_1px_rgba(124,92,252,0.08)]',
            'animate-in slide-in-from-left-2 fade-in duration-200'
          )}
        >
          {/* Arrow/Pointer */}
          <div
            className={cn(
              'absolute -left-[5px] top-1/2 -translate-y-1/2 rotate-45',
              'w-2 h-2 bg-bg-surface/[0.92]',
              'border-l border-b border-border-subtle'
            )}
          />

          {/* Panel Header */}
          <div className="flex items-center justify-between px-2 mb-1 h-8">
            <div className="text-[11px] font-semibold text-text-faint uppercase tracking-wider">
              More Modules
            </div>
            <button
              onClick={() => setIsGroupOpen(false)}
              className="flex items-center justify-center w-5 h-5 text-text-faint hover:text-slate-100 transition-colors duration-200"
            >
              <X size={12} />
            </button>
          </div>

          {/* Divider */}
          <div className="h-px bg-border-subtle mb-1" />

          {/* Group Items */}
          <div className="flex flex-col gap-0.5">
            {groupItems.map((item) => {
              const isActive = item.id === activeGroupItemId;
              const ItemIcon = item.icon;

              return (
                <button
                  key={item.id}
                  onClick={() => {
                    onGroupItemClick?.(item.id);
                    setIsGroupOpen(false);
                  }}
                  className={cn(
                    'group relative flex items-center gap-2.5 px-3 h-10 rounded-[10px] transition-all duration-150',
                    isActive
                      ? 'bg-accent-primary/12'
                      : 'hover:bg-bg-hover'
                  )}
                >
                  {/* Left accent bar */}
                  {isActive && (
                    <div className="absolute left-0 w-[3px] h-5 bg-accent-primary rounded-r-sm" />
                  )}

                  <ItemIcon
                    size={18}
                    className={cn(
                      'transition-colors',
                      isActive
                        ? 'text-accent-primary'
                        : 'text-slate-400 group-hover:text-slate-100'
                    )}
                  />
                  <span
                    className={cn(
                      'text-[13px] transition-colors',
                      isActive
                        ? 'font-semibold text-accent-primary'
                        : 'font-medium text-slate-400 group-hover:text-slate-100'
                    )}
                  >
                    {item.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
