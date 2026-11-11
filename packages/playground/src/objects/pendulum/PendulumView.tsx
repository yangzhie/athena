import { useRef, useState, type CSSProperties, type PointerEvent } from 'react'
import { cn } from '../../core/cn'
import { useBodyDrag } from '../../core/useBodyDrag'
import type { ObjectViewProps } from '../types'
import { GATE, LOWEST, MASSES, PENDULUM, PX_PER_M, type PendulumState } from './module'
import { periodOf } from './physics'

const BOB: Record<number, number> = { 50: 9, 100: 12, 200: 16 }
/** Spare bobs on the base, by mass. (A function: module constants aren't ready at import time.) */
const tray = (i: number) => ({ x: 160 + i * 34, y: 378 })

type Gesture = { kind: 'pivot' } | { kind: 'bob' } | { kind: 'mass'; grams: number; moved: boolean; x0: number; y0: number }

/**
 * A pendulum on a stand, swinging in real time and worked by hand: pull the
 * bob sideways to set the release angle, drag the pivot to change the length,
 * drag a bob from the base onto the string to swap it. Drag the stand to move it.
 */
export function PendulumView({ object, state, dispatch, preview, demonstrating, moveTo, highlight, wiring }: ObjectViewProps<'pendulum', PendulumState>) {
  const drag = useBodyDrag(object.rect, moveTo, demonstrating)
  const svg = useRef<SVGSVGElement>(null)
  const gesture = useRef<Gesture | null>(null)
  /** While the bob is held out: which side it is on (it hangs still until let go). */
  const [held, setHeld] = useState<1 | -1 | null>(null)
  const [carried, setCarried] = useState<{ grams: number; x: number; y: number } | null>(null)
  const id = object.id
  const pivotY = LOWEST.y - state.length * PX_PER_M
  const period = periodOf(state.length, object.config.g, state.amplitude)
  const gated = wiring.peers('gate').length > 0
  const origin = { transformBox: 'view-box', transformOrigin: `${LOWEST.x}px ${pivotY}px` } as CSSProperties
  const swing = held
    ? { ...origin, transform: `rotate(${-held * state.amplitude}deg)` }
    : ({ ...origin, animation: `pg-swing ${period / 2}s ease-in-out infinite alternate`, '--pg-amplitude': `${state.amplitude}deg` } as CSSProperties)
  const ring = (part: string) => highlight?.part === part && 'stroke-warn'

  const local = (e: PointerEvent<Element>) => {
    const box = svg.current!.getBoundingClientRect()
    const k = PENDULUM.w / box.width
    return { x: (e.clientX - box.left) * k, y: (e.clientY - box.top) * k }
  }
  /** Each handle names its gesture in `data-gesture` (and `data-grams` for the spare bobs). */
  const begin = (e: PointerEvent<SVGGElement>) => {
    if (demonstrating) return
    e.stopPropagation()
    e.currentTarget.setPointerCapture(e.pointerId)
    const { gesture: kind, grams } = e.currentTarget.dataset
    const { x: x0, y: y0 } = local(e)
    gesture.current = kind === 'pivot' ? { kind: 'pivot' } : kind === 'bob' ? { kind: 'bob' } : { kind: 'mass', grams: Number(grams), moved: false, x0, y0 }
  }
  const move = (e: PointerEvent<SVGGElement>) => {
    const g = gesture.current
    if (!g) return
    const p = local(e)
    if (g.kind === 'pivot') preview({ type: 'setLength', metres: (LOWEST.y - p.y) / PX_PER_M })
    if (g.kind === 'bob') {
      const angle = (Math.atan2(p.x - LOWEST.x, p.y - pivotY) * 180) / Math.PI
      setHeld(angle < 0 ? -1 : 1)
      preview({ type: 'setAmplitude', degrees: Math.abs(angle) })
    }
    if (g.kind === 'mass') {
      if (!g.moved && Math.hypot(p.x - g.x0, p.y - g.y0) < 4) return
      g.moved = true
      setCarried({ grams: g.grams, ...p })
    }
  }
  const end = (e: PointerEvent<SVGGElement>) => {
    const g = gesture.current
    gesture.current = null
    if (!g) return
    if (g.kind === 'pivot') dispatch({ type: 'setLength', metres: state.length })
    if (g.kind === 'bob') {
      setHeld(null)
      dispatch({ type: 'setAmplitude', degrees: state.amplitude })
    }
    if (g.kind === 'mass') {
      setCarried(null)
      const p = local(e)
      // A tap, or a drop near the bob, hangs this one on the string.
      if (!g.moved || Math.hypot(p.x - LOWEST.x, p.y - LOWEST.y) < 50) dispatch({ type: 'setMass', grams: g.grams })
    }
  }
  const handle = { onPointerDown: begin, onPointerMove: move, onPointerUp: end, onPointerCancel: end, className: 'pointer-events-auto' }

  return (
    <svg ref={svg} width={PENDULUM.w} height={PENDULUM.h} className="overflow-visible select-none">
      {/* Stand: drag it to move the pendulum */}
      <g className={demonstrating ? 'pointer-events-auto' : 'pointer-events-auto cursor-grab active:cursor-grabbing'} data-anchor={`${id}/stand`} {...drag}>
        <rect x={10} y={396} width={240} height={12} rx={3} className="fill-line" />
        <rect x={26} y={pivotY - 8} width={8} height={396 - pivotY + 8} className="fill-muted/60" />
        <rect x={26} y={pivotY - 4} width={LOWEST.x - 22} height={6} rx={2} className="fill-muted/60" />
      </g>
      {/* Length marker */}
      <line x1={LOWEST.x + 34} y1={pivotY} x2={LOWEST.x + 34} y2={LOWEST.y} className="pointer-events-none stroke-muted/50" strokeDasharray="3 3" />
      <text x={LOWEST.x + 40} y={(pivotY + LOWEST.y) / 2} className="pointer-events-none fill-muted font-mono text-[11px]">
        L = {state.length.toFixed(2)} m
      </text>
      {/* String and bob: pull the bob out to the release angle */}
      <g style={swing}>
        <line x1={LOWEST.x} y1={pivotY} x2={LOWEST.x} y2={LOWEST.y} className="pointer-events-none stroke-ink/70" strokeWidth={1.5} />
        <g {...handle} data-gesture="bob" data-anchor={`${id}/bob`} style={{ cursor: demonstrating ? 'default' : 'grab' }}>
          <circle cx={LOWEST.x} cy={LOWEST.y} r={BOB[state.mass] + 8} fill="transparent" />
          <circle cx={LOWEST.x} cy={LOWEST.y} r={BOB[state.mass]} className={cn('fill-accent stroke-ink/40', ring('bob'))} strokeWidth={1.5} />
        </g>
      </g>
      {held && (
        <>
          <path d={`M${LOWEST.x},${pivotY} L${LOWEST.x},${pivotY + 40}`} className="pointer-events-none stroke-muted/60" strokeDasharray="2 3" />
          <text x={LOWEST.x + held * 8} y={pivotY + 54} textAnchor={held > 0 ? 'start' : 'end'} className="pointer-events-none fill-accent font-mono text-[11px]">
            {state.amplitude}°
          </text>
        </>
      )}
      {/* Pivot: drag up or down to change the length */}
      <g {...handle} data-gesture="pivot" data-anchor={`${id}/pivot`} style={{ cursor: demonstrating ? 'default' : 'ns-resize' }}>
        <circle cx={LOWEST.x} cy={pivotY} r={12} className={cn('fill-surface stroke-muted', ring('pivot'))} strokeWidth={1.5} />
        <path d={`M${LOWEST.x - 4},${pivotY - 3} l4,-4 l4,4 M${LOWEST.x - 4},${pivotY + 3} l4,4 l4,-4`} fill="none" className="stroke-muted" strokeWidth={1.5} />
      </g>
      {/* Where the photogate clips on */}
      {!gated && (
        <g data-anchor={`${id}/gate`}>
          <circle cx={GATE.x} cy={GATE.y} r={9} fill="none" className="stroke-muted" strokeWidth={1.5} strokeDasharray="3 3" />
          <text x={GATE.x - 14} y={GATE.y + 4} textAnchor="end" className="pointer-events-none fill-muted text-[10px]">
            photogate here
          </text>
        </g>
      )}
      {/* Spare bobs on the base: drag one onto the string (or tap it) */}
      {MASSES.map((g, i) => (
        <g key={g} {...handle} data-gesture="mass" data-grams={g} data-anchor={`${id}/mass-${g}`} style={{ cursor: demonstrating ? 'default' : 'grab' }}>
          <circle cx={tray(i).x} cy={tray(i).y} r={BOB[g] + 5} fill="transparent" />
          {g === state.mass ? (
            <circle cx={tray(i).x} cy={tray(i).y} r={BOB[g]} fill="none" className={cn('stroke-muted', ring(`mass-${g}`))} strokeDasharray="2 2" />
          ) : (
            <circle cx={tray(i).x} cy={tray(i).y} r={BOB[g]} className={cn('fill-accent/70 stroke-ink/40', ring(`mass-${g}`))} strokeWidth={1.5} />
          )}
          <text x={tray(i).x} y={422} textAnchor="middle" className="pointer-events-none fill-muted font-mono text-[10px]">
            {g} g
          </text>
        </g>
      ))}
      {carried && <circle cx={carried.x} cy={carried.y} r={BOB[carried.grams]} className="pointer-events-none fill-accent/70 stroke-ink/40" strokeWidth={1.5} />}
      <text x={PENDULUM.w - 4} y={12} textAnchor="end" className="pointer-events-none fill-muted text-[10px]">
        pull the bob out · drag the pivot · swap the bob
      </text>
    </svg>
  )
}
