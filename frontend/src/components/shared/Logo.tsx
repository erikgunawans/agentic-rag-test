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

  return <img src={src} alt="LexCore" className={`${filterClass} ${className}`} />
}
