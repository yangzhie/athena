import { useEffect, useState } from 'react'
import { getSourcePassage, sourceFileUrl, type SourcePassage } from '../../../../api/materials'
import { useOffering } from '../../useOffering'
import type { PanelContent } from '../types'

type Props = { content: Extract<PanelContent, { kind: 'source' }> }

/** Resolve the immutable cited passage through its authorised Offering endpoint. */
export function SourceRenderer({ content: { source } }: Props) {
  const offering = useOffering()
  const [passage, setPassage] = useState<SourcePassage | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let active = true
    getSourcePassage(offering.id, source.sourceId, source.passageId).then(result => {
      if (active) setPassage(result)
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : 'Source unavailable.') })
    return () => { active = false }
  }, [offering.id, source.sourceId, source.passageId])
  if (error) return <p className="p-5 text-sm text-bad" role="alert">{error}</p>
  if (!passage) return <p className="p-5 text-sm text-muted">Loading source passage…</p>
  return <div className="space-y-4 p-5">
    <p className="text-xs text-muted">{[passage.filename, `v${passage.version}`, passage.page && `Page ${passage.page}`, passage.section].filter(Boolean).join(' · ')}</p>
    <blockquote className="whitespace-pre-wrap border-l-2 border-accent pl-4 text-[0.9375rem] leading-relaxed">{passage.text}</blockquote>
    <a href={sourceFileUrl(offering.id, source.sourceId)} className="text-sm text-accent underline">Download this source version</a>
  </div>
}
