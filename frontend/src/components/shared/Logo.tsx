import { useTheme } from '@/theme/ThemeContext'

interface LogoProps {
  variant?: 'full' | 'icon'
  className?: string
}

export function Logo({ variant = 'full', className = '' }: LogoProps) {
  const { resolvedTheme } = useTheme()

  // Full wordmark: render the same dark SVG in both themes so size and position match.
  // Light theme uses a CSS filter that inverts luminance while preserving hue —
  // the white "LexCore" text becomes black while the cyan "Core" accent stays cyan.
  if (variant === 'full') {
    const filterStyle =
      resolvedTheme === 'light' ? { filter: 'invert(1) hue-rotate(180deg)' } : undefined
    return (
      <img
        src="/lexcore-dark.svg"
        alt="LexCore"
        className={className}
        style={filterStyle}
      />
    )
  }

  // Icon variant: existing pattern — single dark SVG, recolored via filter for light bg.
  const filterClass = resolvedTheme === 'light' ? 'brightness-[0.15] saturate-[1.5]' : ''
  return (
    <img src="/lexcore-logo-dark.svg" alt="LexCore" className={`${filterClass} ${className}`} />
  )
}
