import type { ChatMessage } from '../../../types'
import { cn } from '../../../lib/cn'

export function MessageBubble({
  message,
  materialTitles,
}: {
  message: ChatMessage
  materialTitles: Record<string, string>
}) {
  const isTutor = message.role === 'tutor'
  return (
    <div className={cn('flex', isTutor ? 'justify-start' : 'justify-end')}>
      <div
        className={cn(
          'max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
          isTutor ? 'rounded-tl-sm border border-line bg-surface' : 'rounded-tr-sm bg-accent text-white',
        )}
      >
        <p>{message.content}</p>
        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {message.citations.map((c) => (
              <span
                key={`${c.materialId}-${c.label}`}
                className="rounded-md bg-line/60 px-2 py-0.5 text-xs text-muted"
                title={materialTitles[c.materialId]}
              >
                {materialTitles[c.materialId] ?? 'Source'} · {c.label}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
