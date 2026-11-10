import { memo } from 'react'
import type { ObjectAction } from '../contracts'
import type { ObjectFrameProps } from './Card'
import { FeedbackBar, ProposalBar } from './chrome'
import { cn } from './cn'

/**
 * A frameless object that lives directly on the canvas, such as two atoms the
 * student drags around or a piece of apparatus. Its empty area lets the canvas pan; only its own
 * shapes take pointer input. Feedback floats underneath.
 */
export const FreeObject = memo(function FreeObject({ object, module, playground, selected, demonstrating, highlight, proposal, peers, wiring }: Omit<ObjectFrameProps, 'zoom'>) {
  const View = module.View
  const dispatch = (action: ObjectAction) => void playground.dispatch({ ...action, objectId: object.id }, 'student')
  const preview = (action: ObjectAction) => void playground.dispatch({ ...action, objectId: object.id }, 'student', { transient: true })
  const { x, y, w, h } = object.rect

  return (
    <div
      data-object={object.id}
      className={cn(
        'pointer-events-none absolute rounded-3xl border-2 border-dashed transition-colors',
        selected ? 'border-accent/50' : highlight ? 'border-warn/70' : 'border-transparent',
      )}
      style={{ left: x, top: y, width: w, height: h }}
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
      <div className="pointer-events-auto absolute top-full left-1/2 mt-1 w-[360px] -translate-x-1/2 space-y-1">
        {proposal && (
          <div className="overflow-hidden rounded-lg border border-line shadow-sm">
            <ProposalBar proposal={proposal} playground={playground} />
          </div>
        )}
        {highlight?.note && <div className="rounded-lg border border-warn/40 bg-warn/10 px-3 py-1.5 text-xs text-warn">{highlight.note}</div>}
        {object.feedback && <FeedbackBar feedback={object.feedback} className="rounded-lg border shadow-sm" />}
      </div>
    </div>
  )
})
