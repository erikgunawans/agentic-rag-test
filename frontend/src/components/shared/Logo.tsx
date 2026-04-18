import { useTheme } from '@/theme/ThemeContext'

interface LogoProps {
  variant?: 'full' | 'icon'
  className?: string
}

export function Logo({ variant = 'full', className = '' }: LogoProps) {
  const { resolvedTheme } = useTheme()
  const src = variant === 'full' ? '/lexcore-new.svg' : '/lexcore-logo-dark.svg'
  const filterClass = resolvedTheme === 'light' ? 'brightness-[0.15] saturate-[1.5]' : ''

  return <img src={src} alt="LexCore" className={`${filterClass} ${className}`} />
}
