import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '../../lib/cn'

export interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  title?: ReactNode
  /** Optional element on the right of the title row, e.g. a Badge or Button. */
  action?: ReactNode
}

export function Card({ title, action, className, children, ...props }: CardProps) {
  return (
    <div className={cn('rounded-lg border border-line bg-surface p-5 shadow-[0_1px_0_var(--color-line),0_8px_24px_-18px_color-mix(in_oklab,var(--color-ink)_35%,transparent)]', className)} {...props}>
      {(title || action) && (
        <div className="mb-3 flex items-center justify-between gap-3">
          {title && <h2 className="text-lg font-semibold">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </div>
  )
}
