import { useEffect, useRef, type PointerEvent } from 'react'
import { cn } from '../../core/cn'
import type { ObjectAction } from '../../contracts'
import type { ObjectViewProps } from '../types'
import { colourLevel, colourName } from './chemistry'
import { bulkPH, flowOf, RIG, type TitrationState } from './module'

// Rig geometry in local (rig) coordinates.
const BX = 200 // burette centre line
const TUBE_TOP = 40
const TUBE_BOTTOM = 400
const TAP = { x: BX, y: 414 }
const TIP_Y = 448
const FLASK = { neck: 468, shoulder: 520, base: 604, half: 78 }
const LIQUID_Y = 560

const flaskPath = `M${BX - 14},${FLASK.neck} L${BX - 14},${FLASK.shoulder} L${BX - FLASK.half},${FLASK.base - 6} Q${BX - FLASK.half},${FLASK.base} ${BX - FLASK.half + 8},${FLASK.base} L${BX + FLASK.half - 8},${FLASK.base} Q${BX + FLASK.half},${FLASK.base} ${BX + FLASK.half},${FLASK.base - 6} L${BX + 14},${FLASK.shoulder} L${BX + 14},${FLASK.neck} Z`

/**
 * A burette over a conical flask, drawn straight onto the canvas. Turn the tap
 * to dispense, shake the flask sideways to swirl it, then record the endpoint.
 */
export function TitrationView({ object, state, dispatch, preview, demonstrating }: ObjectViewProps<'titration', TitrationState>) {
  const config = object.config
  const rect = object.rect
  const svgRef = useRef<SVGSVGElement>(null)
  const tapDrag = useRef<number | null>(null)
  const shake = useRef<{ start: number; last: number; dir: number; extreme: number; reversals: number } | null>(null)

  // Time passes while the tap is open: the burette keeps flowing.
  const previewRef = useRef(preview)
  useEffect(() => {
    previewRef.current = preview
  })
  const flowing = state.opening > 0.02 && !demonstrating
  useEffect(() => {
    if (!flowing) return
    let last = performance.now()
    const timer = setInterval(() => {
      const now = performance.now()
      previewRef.current({ type: 'tick', dt: Math.min(0.5, (now - last) / 1000) })
      last = now
    }, 50)
    return () => clearInterval(timer)
  }, [flowing])

  const local = (e: PointerEvent) => {
    const box = svgRef.current!.getBoundingClientRect()
    return { x: ((e.clientX - box.left) / box.width) * RIG.w, y: ((e.clientY - box.top) / box.height) * RIG.h }
  }

  // Tap: the lever points right when closed and turns down to fully open.
  const tapOpening = (e: PointerEvent) => {
    const p = local(e)
    const deg = (Math.atan2(p.y - TAP.y, p.x - TAP.x) * 180) / Math.PI
    return Math.min(1, Math.max(0, deg / 90))
  }
  const tapHandlers = {
    onPointerDown: (e: PointerEvent) => {
      if (demonstrating) return
      e.currentTarget.setPointerCapture(e.pointerId)
      tapDrag.current = tapOpening(e)
      preview({ type: 'setTap', opening: tapDrag.current })
    },
    onPointerMove: (e: PointerEvent) => {
      if (tapDrag.current === null) return
      tapDrag.current = tapOpening(e)
      preview({ type: 'setTap', opening: tapDrag.current })
    },
    onPointerUp: () => {
      if (tapDrag.current === null) return
      const opening = tapDrag.current < 0.04 ? 0 : tapDrag.current
      tapDrag.current = null
      dispatch({ type: 'dispenseTo', volume: state.volume, mode: flowOf(state.opening) === 'stream' ? 'stream' : 'dropwise' })
      dispatch({ type: 'setTap', opening })
    },
  }

  // Flask: shaking it sideways (several quick reversals) swirls it.
  const flaskHandlers = {
    onPointerDown: (e: PointerEvent) => {
      if (demonstrating) return
      e.currentTarget.setPointerCapture(e.pointerId)
      const x = local(e).x
      shake.current = { start: x, last: x, dir: 0, extreme: x, reversals: 0 }
    },
    onPointerMove: (e: PointerEvent) => {
      const s = shake.current
      if (!s) return
      const x = local(e).x
      const dir = Math.sign(x - s.last)
      if (dir && s.dir && dir !== s.dir && Math.abs(s.last - s.extreme) > 6) {
        s.reversals += 1
        s.extreme = s.last
      }
      if (dir) s.dir = dir
      s.last = x
      preview({ type: 'wobble', dx: Math.max(-22, Math.min(22, x - s.start)) })
      if (s.reversals >= 4) {
        s.reversals = 0
        dispatch({ type: 'swirl' })
      }
    },
    onPointerUp: () => {
      shake.current = null
      preview({ type: 'wobble', dx: 0 })
    },
  }

  const act = (a: ObjectAction) => () => !demonstrating && dispatch(a)

  const pxPerML = (TUBE_BOTTOM - TUBE_TOP) / config.burette.capacity
  const meniscus = TUBE_TOP + state.volume * pxPerML
  const level = colourLevel(config, bulkPH(config, state))
  const colour = colourName(level)
  const flow = flowOf(state.opening)
  const angle = state.opening * 90
  const flash = state.unmixed > 0 ? Math.min(0.85, 0.3 + state.unmixed * 2.5) : 0

  return (
    <svg ref={svgRef} width={rect.w} height={rect.h} viewBox={`0 0 ${RIG.w} ${RIG.h}`} className="overflow-visible">
      <defs>
        <clipPath id={`flask-${object.id}`}>
          <path d={flaskPath} />
        </clipPath>
        <linearGradient id={`glass-${object.id}`} x1="0" x2="1">
          <stop offset="0" stopColor="white" stopOpacity="0.55" />
          <stop offset="0.5" stopColor="white" stopOpacity="0.1" />
          <stop offset="1" stopColor="white" stopOpacity="0.4" />
        </linearGradient>
      </defs>

      {/* Stand */}
      <rect x={40} y={636} width={290} height={14} rx={4} className="fill-muted/40" />
      <rect x={66} y={20} width={8} height={620} rx={3} className="fill-muted/50" />
      <rect x={70} y={96} width={BX - 70 - 8} height={7} rx={3} className="fill-muted/50" />
      <rect x={BX - 16} y={90} width={10} height={20} rx={3} className="fill-muted/70" />

      {/* Burette */}
      <text x={BX} y={18} textAnchor="middle" className="fill-ink text-[12px] font-semibold">
        {config.titrant.label}
      </text>
      <rect x={BX - 11} y={TUBE_TOP} width={22} height={TUBE_BOTTOM - TUBE_TOP} rx={3} className="fill-surface/60 stroke-muted/60" />
      {state.volume < config.burette.capacity && (
        <rect x={BX - 10} y={meniscus} width={20} height={TUBE_BOTTOM - meniscus} className="fill-sky-200/70" />
      )}
      <path d={`M${BX - 10},${meniscus} Q${BX},${meniscus + 5} ${BX + 10},${meniscus}`} className="fill-none stroke-sky-500" strokeWidth={1.5} />
      {Array.from({ length: config.burette.capacity + 1 }, (_, ml) => (
        <g key={ml}>
          <line
            x1={BX - 11}
            x2={BX - 11 + (ml % 5 === 0 ? 9 : 5)}
            y1={TUBE_TOP + ml * pxPerML}
            y2={TUBE_TOP + ml * pxPerML}
            className="stroke-muted"
            strokeWidth={ml % 5 === 0 ? 1.2 : 0.6}
          />
          {ml % 5 === 0 && (
            <text x={BX - 16} y={TUBE_TOP + ml * pxPerML + 3} textAnchor="end" className="fill-muted font-mono text-[9px]">
              {ml}
            </text>
          )}
        </g>
      ))}
      <g transform={`translate(${BX + 18}, ${meniscus})`} className="pointer-events-none">
        <path d="M0,0 L8,-9 L92,-9 L92,9 L8,9 Z" className="fill-surface stroke-sky-500" />
        <text x={50} y={4} textAnchor="middle" className="fill-ink font-mono text-[11px] font-semibold">
          {state.volume.toFixed(2)} mL
        </text>
      </g>

      {/* Tap and tip */}
      <rect x={BX - 3} y={TUBE_BOTTOM} width={6} height={TAP.y - TUBE_BOTTOM} className="fill-surface stroke-muted/60" />
      <rect x={BX - 2} y={TAP.y} width={4} height={TIP_Y - TAP.y} className="fill-surface stroke-muted/60" />
      <g
        data-anchor={`${object.id}/tap`}
        {...tapHandlers}
        className={cn('pointer-events-auto', demonstrating ? 'cursor-default' : 'cursor-grab active:cursor-grabbing')}
      >
        <circle cx={TAP.x} cy={TAP.y} r={34} fill="transparent" />
        <circle cx={TAP.x} cy={TAP.y} r={9} className="fill-surface stroke-ink" strokeWidth={1.5} />
        <g transform={`rotate(${angle} ${TAP.x} ${TAP.y})`}>
          <rect x={TAP.x} y={TAP.y - 4} width={32} height={8} rx={4} className={flow === 'closed' ? 'fill-ink' : 'fill-accent'} />
        </g>
      </g>
      <text x={TAP.x - 18} y={TAP.y + 4} textAnchor="end" className="pointer-events-none fill-muted text-[10px]">
        {flow === 'closed' ? 'tap closed' : flow === 'dropwise' ? 'dropwise' : 'running'}
      </text>

      {/* Titrant on its way down */}
      {flow === 'stream' && state.volume < config.burette.capacity && (
        <line x1={BX} x2={BX + state.wobble} y1={TIP_Y} y2={LIQUID_Y} className="stroke-sky-300" strokeWidth={2.5} />
      )}
      {state.drops > 0 && (
        <circle key={state.drops} cx={BX} cy={TIP_Y + 4} r={3} className="animate-[pg-drop_.38s_ease-in_forwards] fill-sky-300" />
      )}

      {/* Flask */}
      <g
        data-anchor={`${object.id}/flask`}
        transform={`translate(${state.wobble}, 0) rotate(${state.wobble * 0.35} ${BX} ${FLASK.base})`}
        {...flaskHandlers}
        className={cn('pointer-events-auto', demonstrating ? 'cursor-default' : 'cursor-ew-resize')}
      >
        <g clipPath={`url(#flask-${object.id})`}>
          <rect x={BX - FLASK.half} y={LIQUID_Y} width={FLASK.half * 2} height={FLASK.base - LIQUID_Y} className="fill-sky-50" />
          <rect
            x={BX - FLASK.half}
            y={LIQUID_Y}
            width={FLASK.half * 2}
            height={FLASK.base - LIQUID_Y}
            fill="#ec4899"
            fillOpacity={level > 0 ? 0.12 + level * 0.7 : 0}
            className="transition-[fill-opacity] duration-500"
          />
          {flash > 0 && <ellipse cx={BX} cy={LIQUID_Y + 8} rx={Math.min(46, 16 + state.unmixed * 30)} ry={Math.min(10, 5 + state.unmixed * 4)} fill="#ec4899" fillOpacity={flash} />}
          <path d={`M${BX - FLASK.half},${LIQUID_Y} Q${BX - state.wobble},${LIQUID_Y + state.wobble * 0.3} ${BX + FLASK.half},${LIQUID_Y}`} className="fill-none stroke-sky-300" />
        </g>
        <path d={flaskPath} fill={`url(#glass-${object.id})`} className="stroke-muted" strokeWidth={1.5} />
        <rect x={BX - FLASK.half} y={FLASK.neck} width={FLASK.half * 2} height={FLASK.base - FLASK.neck} fill="transparent" />
      </g>
      <text x={BX + FLASK.half + 8} y={LIQUID_Y + 6} className="pointer-events-none fill-muted text-[10px]">
        <tspan x={BX + FLASK.half + 8}>
          {config.analyte.volume.toFixed(2)} mL {config.analyte.concentration.toFixed(3)} M {config.analyte.formula}
        </tspan>
        <tspan x={BX + FLASK.half + 8} dy={13}>
          + {config.indicator.name}
        </tspan>
        <tspan x={BX + FLASK.half + 8} dy={13} className={cn('font-semibold', colour === 'colourless' ? 'fill-muted' : 'fill-pink-500')}>
          {colour}
        </tspan>
      </text>

      {/* Controls, hint and provenance */}
      <foreignObject x={0} y={664} width={RIG.w} height={90}>
        <div className="flex flex-col items-center gap-1.5">
          <div className="pointer-events-auto flex gap-2">
            <button
              type="button"
              data-anchor={`${object.id}/record`}
              onClick={act({ type: 'recordEndpoint' })}
              className="rounded-full bg-accent px-3 py-1 text-xs font-medium text-white shadow-sm hover:opacity-90"
            >
              Record endpoint ({state.volume.toFixed(2)} mL)
            </button>
            <button
              type="button"
              data-anchor={`${object.id}/new-trial`}
              onClick={act({ type: 'newTrial' })}
              className="rounded-full border border-line bg-surface px-3 py-1 text-xs shadow-sm hover:bg-bg"
            >
              New trial
            </button>
          </div>
          <span className="text-[11px] text-muted">
            Trial {state.trial} · turn the tap to dispense · shake the flask sideways to swirl
          </span>
          <span className="rounded bg-warn/15 px-1.5 py-0.5 text-[10px] font-medium text-warn">Simulated · ideal strong acid/base model</span>
        </div>
      </foreignObject>
    </svg>
  )
}
