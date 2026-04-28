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

  // The light wordmark SVG has internal padding that renders the visible content at ~96% of its
  // viewBox; the dark wordmark fills its viewBox more tightly (the embedded image is upscaled
  // and clipped), so they look mismatched at the same `h-N` class. Scale the light variant up to
  // match the dark one's visible footprint. origin-left keeps the left edge anchored so the
  // logo doesn't shift in flex layouts.
  const lightSizeMatch = variant === 'full' && resolvedTheme === 'light' ? 'scale-[1.4] origin-left' : ''

  return <img src={src} alt="LexCore" className={`${filterClass} ${lightSizeMatch} ${className}`} />
}
