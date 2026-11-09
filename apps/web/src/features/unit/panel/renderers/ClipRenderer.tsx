import { formatTimestamp } from '../../../../lib/format'
import type { PanelContent } from '../types'

type Props = { content: Extract<PanelContent, { kind: 'clip' }> }

/**
 * Lecture clip player. Placeholder until playback exists: the real one plays
 * the recording's HLS stream between clip.startS and clip.endS.
 */
export function ClipRenderer({ content: { clip, lecture } }: Props) {
  const start = (clip.startS / lecture.durationS) * 100
  const width = ((clip.endS - clip.startS) / lecture.durationS) * 100

  return (
    <div className="space-y-5 p-5">
      <div className="grid aspect-video place-items-center rounded-xl bg-ink/90 text-bg">
        <div className="text-center">
          <span className="text-3xl" aria-hidden>
            ▶
          </span>
          <p className="mt-2 text-xs opacity-70">Playback not connected yet</p>
        </div>
      </div>

      {/* Where the clip sits in the full lecture. */}
      <div>
        <div className="relative h-2 rounded-full bg-line" aria-hidden>
          <div className="absolute inset-y-0 rounded-full bg-accent" style={{ left: `${start}%`, width: `${width}%` }} />
        </div>
        <div className="mt-1.5 flex justify-between text-xs text-muted tabular-nums">
          <span>
            {formatTimestamp(clip.startS)}–{formatTimestamp(clip.endS)}
          </span>
          <span>of {formatTimestamp(lecture.durationS)}</span>
        </div>
      </div>

      <div>
        <p className="text-xs text-muted">
          Week {lecture.week} · {lecture.title} · {clip.topic}
        </p>
        <p className="mt-1 text-sm">{clip.summary}</p>
      </div>
    </div>
  )
}
