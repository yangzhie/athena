import { Badge, Button } from '../../../components/ui'
import { formatTimestamp } from '../../../lib/format'
import type { LectureClip } from '../../../types'

export function ClipRow({ clip }: { clip: LectureClip }) {
  const minutes = Math.max(1, Math.round((clip.endS - clip.startS) / 60))
  return (
    <li className="flex items-start justify-between gap-4 px-5 py-4">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          <span className="tabular-nums">
            {formatTimestamp(clip.startS)}–{formatTimestamp(clip.endS)}
          </span>
          <span aria-hidden>·</span>
          <span>{minutes} min</span>
          <Badge tone="accent">{clip.topic}</Badge>
        </div>
        <p className="mt-1 font-medium">{clip.title}</p>
        <p className="mt-0.5 text-sm text-muted">{clip.summary}</p>
      </div>
      <Button variant="secondary" size="sm" disabled title="Playback coming soon" className="shrink-0">
        ▶ Play
      </Button>
    </li>
  )
}
