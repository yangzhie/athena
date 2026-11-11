import { useSyncExternalStore } from 'react'
import { cn } from './cn'
import type { Playground } from './store'

/** The agent's visible hand during demonstrations. Lives in screen space. */
export function VirtualHand({ playground }: { playground: Playground }) {
  const hand = useSyncExternalStore(playground.subscribeHand, playground.getHand)
  if (!hand.visible) return null
  return (
    <div className="pointer-events-none absolute top-0 left-0 z-50" style={{ transform: `translate(${hand.x}px, ${hand.y}px)` }}>
      <span
        className={cn(
          'absolute -top-4 -left-4 h-8 w-8 rounded-full bg-accent/25 transition-transform duration-150',
          hand.pressed ? 'scale-100' : 'scale-0',
        )}
      />
      <svg width="30" height="34" viewBox="0 0 30 34" className={cn('-mt-1 -ml-2 drop-shadow-lg transition-transform', hand.pressed && 'scale-90')}>
        <path
          d="M10 2c1.7 0 3 1.3 3 3v10l1-.2V12c0-1.6 1.3-2.8 2.9-2.8S19.8 10.4 19.8 12v3.4l.8-.1c.2-1.4 1.4-2.4 2.8-2.4 1.6 0 2.9 1.3 2.9 2.9v1.5c1-.2 2.7.6 2.7 2.6v4.3C29 29.2 25.2 33 20.2 33h-3.5c-3 0-5.7-1.5-7.4-4L3.6 20.6c-.9-1.3-.6-3.1.7-4s3.1-.6 4 .7L7 15V5c0-1.7 1.3-3 3-3z"
          className="fill-surface stroke-accent"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
      </svg>
      <span className="absolute top-8 left-4 rounded-full bg-accent px-2 py-0.5 text-[10px] whitespace-nowrap text-white shadow">Tutor demo</span>
    </div>
  )
}
