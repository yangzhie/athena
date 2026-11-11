import { cn } from '../../lib/cn'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost'
export type ButtonSize = 'sm' | 'md'

const variants: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-surface shadow-[0_1px_0_color-mix(in_oklab,var(--color-ink)_25%,transparent)] hover:brightness-110',
  secondary: 'border border-line bg-surface text-ink hover:border-ink/30 hover:bg-bg',
  ghost: 'text-muted hover:bg-bg hover:text-ink',
}

const sizes: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-sm',
  md: 'h-10 px-4 text-sm',
}

/** Button classes, for things that look like a button but aren't one (e.g. a <Link>). */
export function buttonStyles(variant: ButtonVariant = 'primary', size: ButtonSize = 'md', className?: string) {
  return cn(
    'inline-flex items-center justify-center gap-2 rounded-md font-semibold transition',
    'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent',
    'disabled:pointer-events-none disabled:opacity-50',
    variants[variant],
    sizes[size],
    className,
  )
}
