import { useTheme } from '@/theme/ThemeContext'

interface LogoProps {
  variant?: 'full' | 'icon'
  className?: string
}

export function Logo({ variant = 'full', className = '' }: LogoProps) {
  const { resolvedTheme } = useTheme()

  let src: string
  if (variant === 'full') {
    src = resolvedTheme === 'light' ? '/lexcore-new-light.svg' : '/lexcore-dark.svg'
  } else {
    src = '/lexcore-logo-dark.svg'
  }

  const filterClass = variant === 'icon' && resolvedTheme === 'light' ? 'brightness-[0.15] saturate-[1.5]' : ''

  // Light wordmark SVG has internal padding so its visible content renders smaller than
  // the dark variant at the same `h-N` class. Wrap in an inline-flex span that holds the
  // requested layout box (so callers' h-N still controls layout) and let the img overflow
  // visually via scale, vertically centered to match the dark variant's apparent size and
  // position.
  if (variant === 'full' && resolvedTheme === 'light') {
    return (
      <span className={`inline-flex items-center overflow-visible ${className}`}>
        <img
          src={src}
          alt="LexCore"
          className="h-full w-auto scale-[1.4] origin-left"
        />
      </span>
    )
  }

  return <img src={src} alt="LexCore" className={`${filterClass} ${className}`} />
}
