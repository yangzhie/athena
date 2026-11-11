import { useState } from 'react'
import { Icon } from '../../../components/ui'
import { listLectures } from '../../../api/lectures'
import { formatTimestamp } from '../../../lib/format'
import type { KnowledgeOrigin, SourceReference } from '../../../types'
import { openInPanel } from '../panel/panelStore'

const originNote: Record<KnowledgeOrigin, string | null> = {
  materials: null,
  supplement: 'Combines cited material with labelled general-knowledge additions.',
  general: 'General knowledge: I couldn’t verify this from the material retrieved for this question.',
}

function label(s: SourceReference) {
  if (s.kind === 'video') return `${s.title} · ${formatTimestamp(s.startS)}`
  return [s.title, s.page && `p. ${s.page}`].filter(Boolean).join(' · ')
}

/** Opens a cited source in the side panel. Video sources resolve to the full clip. */
async function open(offeringId: string, s: SourceReference) {
  if (s.kind === 'document') return openInPanel(offeringId, { kind: 'source', source: s })
  const lecture = (await listLectures(offeringId)).find((l) => l.id === s.sourceId)
  const clip = lecture?.clips.find((c) => c.id === s.segmentId)
  if (!lecture || !clip) throw new Error('This cited clip is unavailable or is no longer approved.')
  openInPanel(offeringId, { kind: 'clip', clip, lecture })
}

export function SourceList({
  offeringId,
  sources = [],
  origin,
  variant = 'chips',
}: {
  offeringId: string
  sources?: SourceReference[]
  origin?: KnowledgeOrigin
  /** chips: a row of buttons under the text. margin: notes written in the page's margin. */
  variant?: 'chips' | 'margin'
}) {
  const [error, setError] = useState<string | null>(null)
  const note = origin ? originNote[origin] : null
  // Several verified quotations can resolve to the same passage or clip. Keep
  // all evidence in storage, but open its full source through one stable chip.
  const keyFor = (s: SourceReference) => `${s.kind}:${s.sourceId}:${s.kind === 'video' ? s.segmentId : s.passageId}`
  const unique = sources.filter((s, index) => sources.findIndex(other => keyFor(other) === keyFor(s)) === index)
  if (sources.length === 0 && !note) return null
  const openSource = (s: SourceReference) => {
    setError(null)
    void open(offeringId, s).catch(e => setError(e instanceof Error ? e.message : 'Source unavailable.'))
  }

  if (variant === 'margin') {
    return (
      <aside className="space-y-3" aria-label="Sources">
        {error && <p role="alert" className="text-xs text-bad">{error}</p>}
        {note && <p className="border-l-2 border-warn/60 pl-3 text-xs text-muted italic">{note}</p>}
        {unique.map((s) => (
          <button
            key={keyFor(s)}
            type="button"
            onClick={() => openSource(s)}
            className="group block w-full border-l-2 border-margin/50 pl-3 text-left transition-colors hover:border-margin"
          >
            <span className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-margin">
              <Icon name={s.kind === 'video' ? 'film' : 'page'} className="size-3.5" />
              {s.kind === 'video' ? formatTimestamp(s.startS) : s.page ? `p. ${s.page}` : 'Source'}
            </span>
            <span className="mt-0.5 block font-serif text-sm leading-snug text-ink group-hover:underline">{s.title}</span>
            {s.quote && <span className="mt-1 line-clamp-3 text-xs text-muted italic">“{s.quote}”</span>}
          </button>
        ))}
      </aside>
    )
  }

  return (
    <div className="mt-3 space-y-2">
      {error && <p role="alert" className="text-xs text-bad">{error}</p>}
      {note && <p className="text-xs text-muted">ⓘ {note}</p>}
      {sources.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label="Sources">
          {unique.map((s) => (
            <li key={keyFor(s)}>
              <button
                type="button"
                onClick={() => openSource(s)}
                title={s.quote}
                className="inline-flex max-w-72 items-center gap-1.5 rounded-md border border-line bg-surface px-2.5 py-1 text-xs text-muted transition-colors hover:border-margin hover:text-ink"
              >
                <Icon name={s.kind === 'video' ? 'film' : 'page'} className="size-3.5 text-margin" />
                <span className="truncate">{label(s)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
