import { Button } from '../../../components/ui'
import { formatTimestamp } from '../../../lib/format'
import type { LectureClip } from '../../../types'

export function ClipList({ clips, topicTitles }: { clips: LectureClip[]; topicTitles: Record<string, string> }) {
  return (
    <ol className="space-y-3">
      {clips.map((clip) => (
        <li key={clip.id} className="flex items-start justify-between gap-4 rounded-lg border border-line p-4">
          <div className="min-w-0">
            <p className="text-xs text-muted tabular-nums">
              {formatTimestamp(clip.startS)}–{formatTimestamp(clip.endS)} · {topicTitles[clip.topicId] ?? clip.topicId}
            </p>
            <p className="mt-0.5 font-medium">{clip.title}</p>
            <p className="mt-1 text-sm text-muted">{clip.summary}</p>
          </div>
          <Button variant="secondary" size="sm" disabled title="Playback coming soon">
            ▶ Play
          </Button>
        </li>
      ))}
    </ol>
  )
}
