import { Fragment } from 'react'
import type { ObjectViewProps } from '../types'

/** Renders `code` and **bold** inline; blank lines split paragraphs. Nothing else. */
function inline(text: string) {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).map((part, i) => {
    if (part.startsWith('`')) return <code key={i} className="rounded bg-bg px-1 font-mono text-[0.9em]">{part.slice(1, -1)}</code>
    if (part.startsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>
    return <Fragment key={i}>{part}</Fragment>
  })
}

export function NoteView({ object }: ObjectViewProps<'note', null>) {
  return (
    <div className="space-y-2 p-3 text-sm leading-relaxed">
      {object.config.markdown.split(/\n{2,}/).map((p, i) => (
        <p key={i}>{inline(p)}</p>
      ))}
    </div>
  )
}
