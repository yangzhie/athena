import { useEffect, useRef, useSyncExternalStore, type ComponentProps, type PointerEvent } from 'react'
import { Card } from './core/Card'
import { FreeObject } from './core/FreeObject'
import { cn } from './core/cn'
import { LinkLayer } from './core/LinkLayer'
import type { Playground } from './core/store'
import { NO_WIRING, type CanvasObject } from './objects/types'
import { VirtualHand } from './core/VirtualHand'
import { WireLayer } from './core/WireLayer'

const NO_PEERS: CanvasObject[] = []

type Props = {
  playground: Playground
  className?: string
}

/**
 * The embeddable Playground Canvas: a DOM canvas with world coordinates and a
 * zoomable viewport. Drag a card by its title bar; interact with its content
 * directly; drag the background to pan; ctrl/⌘ + wheel (or pinch) to zoom.
 */
export function LearningCanvas({ playground, className }: Props) {
  const state = useSyncExternalStore(playground.subscribe, playground.getState)
  const rootRef = useRef<HTMLDivElement>(null)
  const pan = useRef<{ x: number; y: number; vx: number; vy: number; moved: boolean } | null>(null)
  const { viewport, objects, order, links, selection, highlight, proposals, demonstrating, scene, goalReached } = state

  useEffect(() => {
    const el = rootRef.current
    if (!el) return
    playground.attach(el)
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const rect = el.getBoundingClientRect()
      const v = playground.getState().viewport
      if (e.ctrlKey || e.metaKey) {
        playground.zoomBy(Math.exp(-e.deltaY * 0.01), e.clientX - rect.left, e.clientY - rect.top)
      } else {
        playground.setViewport({ ...v, x: v.x - e.deltaX, y: v.y - e.deltaY })
      }
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => {
      el.removeEventListener('wheel', onWheel)
      playground.attach(null)
    }
  }, [playground])

  const onDown = (e: PointerEvent) => {
    if (e.button !== 0) return
    e.currentTarget.setPointerCapture(e.pointerId)
    pan.current = { x: e.clientX, y: e.clientY, vx: viewport.x, vy: viewport.y, moved: false }
  }
  const onMove = (e: PointerEvent) => {
    const p = pan.current
    if (!p) return
    const dx = e.clientX - p.x
    const dy = e.clientY - p.y
    if (Math.abs(dx) + Math.abs(dy) > 3) p.moved = true
    if (p.moved) playground.setViewport({ ...viewport, x: p.vx + dx, y: p.vy + dy })
  }
  const onUp = () => {
    if (pan.current && !pan.current.moved) playground.select(null)
    pan.current = null
  }

  const rects = Object.fromEntries(order.map((id) => [id, objects[id].rect]))
  // Objects that share an experiment see each other (e.g. a readout and its lab).
  const experiments = new Map<string, CanvasObject[]>()
  order.forEach((id) => {
    const e = objects[id].experimentId
    if (e) experiments.set(e, [...(experiments.get(e) ?? []), objects[id]])
  })
  const peersOf = (o: CanvasObject) => (o.experimentId ? experiments.get(o.experimentId)!.filter((p) => p.id !== o.id) : NO_PEERS)
  const grid = 24 * viewport.zoom

  return (
    <div
      ref={rootRef}
      className={cn('relative h-full w-full touch-none overflow-hidden bg-bg select-none', className)}
      style={{
        backgroundImage: 'radial-gradient(var(--color-line) 1.2px, transparent 1.2px)',
        backgroundSize: `${grid}px ${grid}px`,
        backgroundPosition: `${viewport.x}px ${viewport.y}px`,
      }}
      onPointerDown={onDown}
      onPointerMove={onMove}
      onPointerUp={onUp}
      onPointerCancel={onUp}
    >
      <div
        className="absolute top-0 left-0 origin-top-left"
        style={{ transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})` }}
      >
        <LinkLayer links={links} rects={rects} />
        {order.map((id) => {
          const o = objects[id]
          const module = playground.module(o.type)
          const props = {
            object: o,
            module,
            playground,
            selected: selection === id,
            demonstrating: demonstrating === id,
            highlight: highlight?.objectId === id ? highlight : null,
            proposal: proposals.find((p) => p.objectId === id),
            peers: peersOf(o),
            wiring: module.ports ? playground.wiring(id) : NO_WIRING,
          }
          return module.bounds || module.size ? <FreeObject key={id} {...props} /> : <Card key={id} {...props} zoom={viewport.zoom} />
        })}
        <WireLayer playground={playground} state={state} />
      </div>

      {scene && (
        <div
          className="absolute top-3 left-3 max-w-md rounded-xl border border-line bg-surface/90 px-3 py-2 shadow-sm backdrop-blur"
          onPointerDown={(e) => e.stopPropagation()}
        >
          <p className="text-[11px] text-muted">{scene.title}</p>
          <p className="text-sm font-medium">
            🎯 {scene.goal}
            {goalReached && <span className="ml-2 rounded-full bg-good/15 px-2 py-0.5 text-xs text-good">Done</span>}
          </p>
        </div>
      )}

      {!order.length && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <p className="text-sm text-muted">The Playground is empty. Ask the tutor a question and it will set up an experiment here.</p>
        </div>
      )}

      <div
        className="absolute bottom-3 left-3 flex items-center gap-1 rounded-lg border border-line bg-surface/90 p-1 text-xs shadow-sm backdrop-blur"
        onPointerDown={(e) => e.stopPropagation()}
      >
        <ToolButton title="Zoom out" onClick={() => playground.zoomBy(1 / 1.2)}>
          −
        </ToolButton>
        <span className="w-10 text-center font-mono text-muted">{Math.round(viewport.zoom * 100)}%</span>
        <ToolButton title="Zoom in" onClick={() => playground.zoomBy(1.2)}>
          +
        </ToolButton>
        <ToolButton title="Fit everything" onClick={() => playground.fitView()}>
          Fit all
        </ToolButton>
        <ToolButton title="Show the selected object" disabled={!selection} onClick={() => selection && playground.focusObject(selection)}>
          Find selected
        </ToolButton>
      </div>

      <VirtualHand playground={playground} />
    </div>
  )
}

function ToolButton({ children, ...props }: ComponentProps<'button'>) {
  return (
    <button type="button" className="rounded px-2 py-1 hover:bg-bg disabled:opacity-40" {...props}>
      {children}
    </button>
  )
}
