import { memo, useEffect, useRef, type PointerEvent } from 'react'
import type { Highlight, ObjectAction, Proposal } from '../contracts'
import type { AnyModule, CanvasObject, Wiring } from '../objects/types'
import { FeedbackBar, ProposalBar, ProvenanceTag } from './chrome'
import { cn } from './cn'
import type { Playground } from './store'

export type ObjectFrameProps = {
  object: CanvasObject
  module: AnyModule
  playground: Playground
  zoom: number
  selected: boolean
  demonstrating: boolean
  highlight: Highlight | null
  proposal: Proposal | undefined
  peers: CanvasObject[]
  wiring: Wiring
}

/** A carded object: drag the title bar to move it, interact with the content directly. */
export const Card = memo(function Card({ object, module, playground, zoom, selected, demonstrating, highlight, proposal, peers, wiring }: ObjectFrameProps) {
  const ref = useRef<HTMLDivElement>(null)
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null)
  const View = module.View

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(() => playground.setObjectSize(object.id, el.offsetWidth, el.offsetHeight))
    ro.observe(el)
    return () => ro.disconnect()
  }, [playground, object.id])

  const onTitleDown = (e: PointerEvent) => {
    if ((e.target as HTMLElement).closest('button')) return
    e.stopPropagation()
    e.currentTarget.setPointerCapture(e.pointerId)
    drag.current = { x: e.clientX, y: e.clientY, ox: object.rect.x, oy: object.rect.y }
    playground.select(object.id)
  }
  const onTitleMove = (e: PointerEvent) => {
    const d = drag.current
    if (!d) return
    playground.moveObject(object.id, d.ox + (e.clientX - d.x) / zoom, d.oy + (e.clientY - d.y) / zoom)
  }
  const onTitleUp = () => {
    drag.current = null
  }

  const dispatch = (action: ObjectAction) => void playground.dispatch({ ...action, objectId: object.id }, 'student')
  const preview = (action: ObjectAction) => void playground.dispatch({ ...action, objectId: object.id }, 'student', { transient: true })

  return (
    <div
      ref={ref}
      data-object={object.id}
      className={cn(
        'absolute flex flex-col rounded-xl border bg-surface shadow-md transition-shadow',
        selected ? 'border-accent shadow-lg ring-2 ring-accent/30' : 'border-line',
        highlight && 'ring-4 ring-warn/60',
        demonstrating && 'ring-2 ring-accent',
      )}
      style={{ left: object.rect.x, top: object.rect.y, width: object.rect.w }}
    >
      <div
        className="flex cursor-grab items-center gap-2 rounded-t-xl border-b border-line px-3 py-2 active:cursor-grabbing"
        onPointerDown={onTitleDown}
        onPointerMove={onTitleMove}
        onPointerUp={onTitleUp}
        onPointerCancel={onTitleUp}
      >
        <span className="text-[11px] text-muted">{module.label}</span>
        <h3 className="min-w-0 flex-1 truncate text-sm font-semibold">{object.title}</h3>
        <ProvenanceTag provenance={object.provenance} />
        {object.modifiedBy === 'student' && <span className="shrink-0 text-[10px] text-muted">edited</span>}
        <button
          type="button"
          title="Remove"
          onClick={() => playground.removeObject(object.id)}
          className="shrink-0 rounded px-1 text-muted hover:bg-bg hover:text-ink"
        >
          ×
        </button>
      </div>

      {proposal && <ProposalBar proposal={proposal} playground={playground} />}
      {highlight?.note && <div className="border-b border-warn/40 bg-warn/10 px-3 py-1.5 text-xs text-warn">{highlight.note}</div>}
      {object.feedback && <FeedbackBar feedback={object.feedback} className="border-b" />}

      <div
        className="relative min-h-0"
        onPointerDown={(e) => {
          e.stopPropagation()
          playground.select(object.id)
        }}
      >
        <View
          object={object}
          state={object.state}
          dispatch={dispatch}
          preview={preview}
          demonstrating={demonstrating}
          highlight={highlight}
          peers={peers}
          wiring={wiring}
          moveTo={(x, y) => playground.moveObject(object.id, x, y)}
        />
        {demonstrating && <div className="pointer-events-auto absolute inset-0 rounded-b-xl" title="The tutor is demonstrating" aria-hidden />}
      </div>
    </div>
  )
})
