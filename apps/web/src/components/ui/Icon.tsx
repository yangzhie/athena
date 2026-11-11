import { cn } from '../../lib/cn'

/** Small line icons drawn like pen marks, used instead of emoji in navigation. */
const PATHS = {
  plus: 'M12 5v14M5 12h14',
  book: 'M5 4.5h9.5A2.5 2.5 0 0 1 17 7v12.5H7.5A2.5 2.5 0 0 1 5 17zM5 17a2.5 2.5 0 0 1 2.5-2.5H17M9 8h5',
  film: 'M4 6.5h16v11H4zM4 10h16M8 6.5v3.5M12 6.5v3.5M16 6.5v3.5M10.5 12.5l3.5 2-3.5 2z',
  cards: 'M7 8.5h11v10H7zM5 15.5v-10h11',
  chart: 'M4.5 19.5h15M7 16v-5M11 16V7M15 16v-7M19 16v-3',
  list: 'M9 7h10M9 12h10M9 17h10M5 7l.01 0M5 12l.01 0M5 17l.01 0',
  chat: 'M5 5.5h14v10H10l-4 3.5v-3.5H5z',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  page: 'M7 3.5h7l4 4v13H7zM14 3.5v4h4M9.5 12h6M9.5 15.5h6',
  flask: 'M10 3.5h4M10.5 3.5v6L5.5 18a1.8 1.8 0 0 0 1.6 2.5h9.8a1.8 1.8 0 0 0 1.6-2.5l-5-8.5v-6M8 14.5h8',
} as const

export type IconName = keyof typeof PATHS

export function Icon({ name, className }: { name: IconName; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={cn('size-[1.1rem] shrink-0', className)} fill="none" stroke="currentColor"
      strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={PATHS[name]} />
    </svg>
  )
}
