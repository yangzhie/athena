import type { PanelContent } from '../types'

type Props = { content: Extract<PanelContent, { kind: 'source' }> }

/** A cited passage from a course document. The full document viewer comes later. */
export function SourceRenderer({ content: { source } }: Props) {
  return (
    <div className="space-y-4 p-5">
      <p className="text-xs text-muted">
        {[source.page && `Page ${source.page}`, source.section].filter(Boolean).join(' · ')}
      </p>
      <blockquote className="border-l-2 border-accent pl-4 text-[0.9375rem] leading-relaxed">{source.quote}</blockquote>
      <p className="text-xs text-muted">Opening the full document isn't connected yet.</p>
    </div>
  )
}
