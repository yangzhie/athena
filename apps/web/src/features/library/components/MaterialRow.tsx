import { Badge, type Tone } from '../../../components/ui'
import { formatDate } from '../../../lib/format'
import type { Material, MaterialKind, MaterialStatus } from '../../../types'

const kindIcon: Record<MaterialKind, string> = { pdf: '📄', slides: '📊', doc: '📝', recording: '🎬' }
const statusTone: Record<MaterialStatus, Tone> = { ready: 'good', processing: 'warn', failed: 'bad' }

export function MaterialRow({ material, topicTitles }: { material: Material; topicTitles: Record<string, string> }) {
  return (
    <li className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-center gap-3">
        <span className="text-xl" aria-hidden>
          {kindIcon[material.kind]}
        </span>
        <div className="min-w-0">
          <p className="truncate font-medium">{material.title}</p>
          <p className="text-xs text-muted">Added {formatDate(material.uploadedAt)}</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5 sm:justify-end">
        {material.topicIds.map((id) => (
          <Badge key={id} tone="accent">
            {topicTitles[id] ?? id}
          </Badge>
        ))}
        <Badge tone={statusTone[material.status]}>{material.status}</Badge>
      </div>
    </li>
  )
}
