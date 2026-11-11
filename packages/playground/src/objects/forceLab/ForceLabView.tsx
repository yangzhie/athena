import { useRef, type PointerEvent } from 'react'
import { cn } from '../../core/cn'
import type { ObjectViewProps } from '../types'
import { forceAt, REGIME_LABEL, regimeAt, type Regime } from './curve'
import { distanceOf, type ForceLabState } from './module'

const REGIME_STYLE: Record<Regime, string> = {
  repulsive: 'bg-bad/15 text-bad border-bad/30',
  balanced: 'bg-good/15 text-good border-good/30',
  attractive: 'bg-accent-soft text-accent border-accent/30',
  negligible: 'bg-surface text-muted border-line',
}

const arrowLength = (f: number) => Math.min(90, 15 * Math.log2(1 + Math.abs(f)))

/**
 * Two particles drawn straight onto the canvas (no card). Drag either one
 * anywhere; the force between them is shown on the canvas itself.
 */
export function ForceLabView({ object, state, dispatch, preview, demonstrating }: ObjectViewProps<'force-lab', ForceLabState>) {
  const { curve, particles: specs } = object.config
  const rect = object.rect
  const svgRef = useRef<SVGSVGElement>(null)
  const grab = useRef<{ index: 0 | 1; dx: number; dy: number; last: { x: number; y: number } | null } | null>(null)

  const r = distanceOf(state)
  const f = forceAt(curve, r)
  const regime = regimeAt(curve, r)
  const [a, b] = state.particles.map((p) => ({ x: p.x - rect.x, y: p.y - rect.y }))
  const len = Math.hypot(b.x - a.x, b.y - a.y) || 1
  const ux = (b.x - a.x) / len // unit vector A → B
  const uy = (b.y - a.y) / len
  const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
  // Offset the distance label perpendicular to the A–B line, towards the top of the screen.
  const nx = uy > 0 ? uy : -uy
  const ny = uy > 0 ? -ux : ux
  const toWorld = (clientX: number, clientY: number) => {
    const box = svgRef.current!.getBoundingClientRect()
    return { x: rect.x + ((clientX - box.left) / box.width) * rect.w, y: rect.y + ((clientY - box.top) / box.height) * rect.h }
  }

  const onDown = (e: PointerEvent, index: 0 | 1) => {
    if (demonstrating) return
    e.currentTarget.setPointerCapture(e.pointerId)
    const p = toWorld(e.clientX, e.clientY)
    const c = state.particles[index]
    grab.current = { index, dx: p.x - c.x, dy: p.y - c.y, last: null }
  }
  const onMove = (e: PointerEvent) => {
    const g = grab.current
    if (!g) return
    const p = toWorld(e.clientX, e.clientY)
    g.last = { x: p.x - g.dx, y: p.y - g.dy }
    preview({ type: 'moveParticle', index: g.index, ...g.last })
  }
  const onUp = () => {
    const g = grab.current
    grab.current = null
    if (g?.last) dispatch({ type: 'moveParticle', index: g.index, ...g.last })
  }

  const arrow = arrowLength(f)
  const dir = f > 0 ? 1 : -1 // repulsion pushes the particles apart
  const arrowClass = f > 0 ? 'stroke-bad' : 'stroke-accent'
  const top = Math.min(a.y, b.y) - Math.max(...state.radii)
  const bottom = Math.max(a.y, b.y) + Math.max(...state.radii)

  return (
    <svg ref={svgRef} width={rect.w} height={rect.h} className="overflow-visible">
      <defs>
        <marker id={`fa-${object.id}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" className={f > 0 ? 'fill-bad' : 'fill-accent'} />
        </marker>
        {specs.map((s, i) => (
          <radialGradient key={i} id={`g${i}-${object.id}`} cx="35%" cy="35%">
            <stop offset="0%" stopColor="white" stopOpacity="0.75" />
            <stop offset="100%" stopColor={s.color} />
          </radialGradient>
        ))}
      </defs>

      {/* The line between the particles and the distance */}
      <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="stroke-muted/50" strokeDasharray="3 5" />
      <text
        x={mid.x + nx * 18}
        y={mid.y + ny * 18}
        textAnchor="middle"
        className="pointer-events-none fill-muted font-mono text-[12px]"
      >
        r = {r.toFixed(3)} nm
      </text>

      {/* Force arrows along the line */}
      {arrow > 2 &&
        (
          [
            [a, -1, state.radii[0]],
            [b, 1, state.radii[1]],
          ] as const
        ).map(([p, side, rad], i) => (
          <line
            key={i}
            x1={p.x + side * dir * ux * rad}
            y1={p.y + side * dir * uy * rad}
            x2={p.x + side * dir * ux * (rad + arrow)}
            y2={p.y + side * dir * uy * (rad + arrow)}
            strokeWidth={5}
            strokeLinecap="round"
            className={cn('pointer-events-none', arrowClass)}
            markerEnd={`url(#fa-${object.id})`}
          />
        ))}

      {/* Particles */}
      {[a, b].map((p, i) => (
        <g
          key={i}
          data-anchor={`${object.id}/particle-${i}`}
          className={cn('pointer-events-auto', demonstrating ? 'cursor-default' : 'cursor-grab active:cursor-grabbing')}
          onPointerDown={(e) => onDown(e, i as 0 | 1)}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerCancel={onUp}
        >
          <circle cx={p.x} cy={p.y} r={state.radii[i] + 10} fill="transparent" />
          <circle cx={p.x} cy={p.y} r={state.radii[i]} fill={`url(#g${i}-${object.id})`} className="drop-shadow-md" />
          <text x={p.x} y={p.y + 5} textAnchor="middle" className="pointer-events-none fill-white text-[15px] font-semibold">
            {specs[i].label}
          </text>
        </g>
      ))}

      {/* Regime label above the pair; hint and provenance below */}
      <foreignObject x={mid.x - 120} y={top - 64} width={240} height={30} className="pointer-events-none">
        <div className="flex h-full items-center justify-center">
          <span className={cn('rounded-full border px-3 py-0.5 text-xs font-semibold shadow-sm', REGIME_STYLE[regime])}>
            {REGIME_LABEL[regime]}
          </span>
        </div>
      </foreignObject>
      <foreignObject x={mid.x - 150} y={bottom + 30} width={300} height={46} className="pointer-events-none">
        <div className="flex h-full flex-col items-center justify-center gap-1 text-center">
          {!demonstrating && <span className="text-[11px] text-muted">Drag either atom</span>}
          <span className="rounded bg-warn/15 px-1.5 py-0.5 text-[10px] font-medium text-warn">AI estimate · demo only</span>
        </div>
      </foreignObject>
    </svg>
  )
}
