import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export type Tone = 'neutral' | 'accent' | 'good' | 'warn' | 'bad'

const tones: Record<Tone, string> = {
  neutral: 'bg-line/60 text-muted',
  accent: 'bg-accent-soft text-accent',
  good: 'bg-good/15 text-good',
  warn: 'bg-warn/15 text-warn',
  bad: 'bg-bad/15 text-bad',
}

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', tones[tone])}>
      {children}
    </span>
  )
}
