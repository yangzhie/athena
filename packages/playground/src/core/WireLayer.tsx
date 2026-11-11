import { useState, type PointerEvent } from 'react'
import type { ObjectId, PortKind } from '../contracts'
import type { CanvasObject, PortSpec } from '../objects/types'
import { cn } from './cn'
import { nearestSocket, plugTip, socketsOfKind, worldPoint } from './ports'
import type { Playground, PlaygroundState } from './store'

type Point = { x: number; y: number }
type Drag = { objectId: ObjectId; plug: string; kind: PortKind; x: number; y: number }

const LEAD: Record<string, string> = { red: '#e11d48', black: '#3f3f46' }

/** The curve a lead, tube or cable follows from where it leaves its object to its tip. */
function path(look: PortSpec['look'], o: Point, t: Point) {
  if (look === 'data') return `M${o.x},${o.y} C${o.x + 70},${o.y} ${t.x - 70},${t.y} ${t.x},${t.y}`
  if (look === 'tube') return `M${o.x},${o.y} C${o.x + (t.x - o.x) * 0.7},${o.y - 10} ${t.x},${t.y - 70} ${t.x},${t.y}`
  const sag = Math.max(40, Math.abs(t.x - o.x) * 0.3)
  return `M${o.x},${o.y} C${o.x},${o.y + sag} ${t.x},${t.y - sag} ${t.x},${t.y}`
}

/**
 * Leads, tubes and cables between objects, in world coordinates above the
 * objects. Drag a plug's tip onto a socket of the same kind to connect it;
 * drop it anywhere else to unplug.
 */
export function WireLayer({ playground, state }: { playground: Playground; state: PlaygroundState }) {
  const [drag, setDrag] = useState<Drag | null>(null)
  const { objects, order, viewport, demonstrating } = state
  const moduleOf = (o: CanvasObject) => playground.module(o.type)

  // The layer's <svg> sits at the world origin, so its screen position converts pointer coordinates.
  const toWorld = (e: PointerEvent) => {
    const box = (e.currentTarget as SVGGraphicsElement).ownerSVGElement!.getBoundingClientRect()
    return { x: (e.clientX - box.left) / viewport.zoom, y: (e.clientY - box.top) / viewport.zoom }
  }
  const onDown = (e: PointerEvent, objectId: ObjectId, plug: string, kind: PortKind) => {
    if (demonstrating) return
    e.stopPropagation()
    e.currentTarget.setPointerCapture(e.pointerId)
    playground.select(objectId)
    setDrag({ objectId, plug, kind, ...toWorld(e) })
  }
  const onMove = (e: PointerEvent) => {
    if (drag) setDrag({ ...drag, ...toWorld(e) })
  }
  const onUp = () => {
    if (!drag) return
    const to = nearestSocket(objects, order, moduleOf, drag.kind, drag.objectId, drag)
    const current = objects[drag.objectId]?.plugs[drag.plug] ?? null
    setDrag(null)
    if (to?.objectId !== current?.objectId || to?.port !== current?.port) {
      void playground.dispatch({ type: 'connect', plug: drag.plug, to, objectId: drag.objectId }, 'student')
    }
  }

  const sockets = drag ? socketsOfKind(objects, order, moduleOf, drag.kind, drag.objectId) : []
  const target = drag && nearestSocket(objects, order, moduleOf, drag.kind, drag.objectId, drag)

  return (
    <svg className="pointer-events-none absolute top-0 left-0 overflow-visible" width={1} height={1}>
      {/* Data sockets on cards (apparatus draws its own sockets) */}
      {order.flatMap((id) =>
        Object.entries(moduleOf(objects[id]).ports ?? {})
          .filter(([, p]) => p.role === 'socket' && p.kind === 'data')
          .map(([port, p]) => {
            const at = worldPoint(objects[id], p.at)
            return (
              <g key={`${id}/${port}`} data-anchor={`${id}/socket:${port}`}>
                <circle cx={at.x} cy={at.y} r={9} className="fill-surface stroke-muted" strokeWidth={2} />
                <circle cx={at.x} cy={at.y} r={3.5} className="fill-muted" />
              </g>
            )
          }),
      )}

      {/* Compatible sockets while a plug is being dragged */}
      {sockets.map((s) => (
        <circle
          key={`${s.ref.objectId}/${s.ref.port}`}
          cx={s.x}
          cy={s.y}
          r={target?.objectId === s.ref.objectId && target.port === s.ref.port ? 20 : 15}
          className="fill-accent/10 stroke-accent"
          strokeWidth={2}
          strokeDasharray="4 4"
        />
      ))}

      {order.flatMap((id) => {
        const o = objects[id]
        return Object.entries(moduleOf(o).ports ?? {})
          .filter(([, p]) => p.role === 'plug')
          .map(([plug, p]) => {
            const origin = worldPoint(o, p.at)
            const tip = drag?.objectId === id && drag.plug === plug ? drag : plugTip(objects, moduleOf, o, plug)
            const d = path(p.look, origin, tip)
            const plugged = Boolean(o.plugs[plug]) && !(drag?.objectId === id && drag.plug === plug) && o.plugDrag?.plug !== plug
            return (
              <g key={`${id}/${plug}`}>
                {p.look === 'tube' ? (
                  <>
                    <path d={d} fill="none" strokeWidth={16} strokeLinecap="round" stroke="#94a3b8" strokeOpacity={0.55} />
                    <path d={d} fill="none" strokeWidth={9} strokeLinecap="round" stroke="#e0f2fe" strokeOpacity={0.9} />
                  </>
                ) : p.look === 'data' ? (
                  <path d={d} fill="none" strokeWidth={2.5} strokeDasharray="6 5" className="stroke-muted" />
                ) : (
                  <path d={d} fill="none" strokeWidth={3.5} strokeLinecap="round" stroke={LEAD[p.look ?? 'black']} />
                )}
                <g
                  data-anchor={`${id}/plug:${plug}`}
                  className={cn('pointer-events-auto', demonstrating ? 'cursor-default' : 'cursor-grab active:cursor-grabbing')}
                  onPointerDown={(e) => onDown(e, id, plug, p.kind)}
                  onPointerMove={onMove}
                  onPointerUp={onUp}
                  onPointerCancel={onUp}
                >
                  <circle cx={tip.x} cy={tip.y} r={16} fill="transparent" />
                  {p.look === 'tube' ? (
                    <rect x={tip.x - 7} y={tip.y - 14} width={14} height={20} rx={6} fill="#e0f2fe" stroke="#94a3b8" strokeWidth={2} />
                  ) : p.look === 'data' ? (
                    <rect x={tip.x - 8} y={tip.y - 6} width={16} height={12} rx={2} className="fill-surface stroke-muted" strokeWidth={2} />
                  ) : (
                    <>
                      <rect x={tip.x - 5} y={tip.y - 20} width={10} height={16} rx={3} fill={LEAD[p.look ?? 'black']} />
                      <path d={`M${tip.x - 6},${tip.y - 5} L${tip.x},${tip.y + 4} L${tip.x + 6},${tip.y - 5}`} fill="#a1a1aa" />
                    </>
                  )}
                  {!plugged && p.label && (
                    <text x={tip.x} y={tip.y + 22} textAnchor="middle" className="pointer-events-none fill-muted text-[10px]">
                      {p.label}
                    </text>
                  )}
                </g>
              </g>
            )
          })
      })}
    </svg>
  )
}
