export type MasteryLevel = 'mastered' | 'learning' | 'gap'

/** Single source of truth for mastery thresholds. */
export const MASTERED = 0.8
export const LEARNING = 0.4

export function masteryLevel(estimate: number): MasteryLevel {
  if (estimate >= MASTERED) return 'mastered'
  if (estimate >= LEARNING) return 'learning'
  return 'gap'
}

/**
 * Status colours are never the only signal (amber and red are hard to tell
 * apart, especially with colour blindness), so each level has an icon + label.
 */
export const masteryMeta: Record<MasteryLevel, { label: string; icon: string; bar: string; text: string }> = {
  mastered: { label: 'Mastered', icon: '✓', bar: 'bg-good', text: 'text-good' },
  learning: { label: 'Learning', icon: '◐', bar: 'bg-warn', text: 'text-warn' },
  gap: { label: 'Gap', icon: '○', bar: 'bg-bad', text: 'text-bad' },
}
